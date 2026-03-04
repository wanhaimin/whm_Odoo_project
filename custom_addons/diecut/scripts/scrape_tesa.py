# scripts/scrape_tesa.py
# =========================================================================
# 德莎 (Tesa) 产品数据采集工具
# 功能：
#   1. 从 tesa 官网爬取产品页面 (HTML)
#   2. 自动下载 TDS PDF 技术资料
#   3. 解析本地已有的 TDS PDF 文件
#   4. 输出为 series.csv / variants.csv 格式，供 generate_catalog.py 使用
#
# 使用方式：
#   python scrape_tesa.py --mode web    # 从官网爬取 (BFS 自动发现新型号)
#   python scrape_tesa.py --mode pdf    # 解析本地 PDF 文件夹
#   python scrape_tesa.py --mode all    # 先爬网页，再解析下载的 PDF
#
# 依赖安装：
#   pip install requests beautifulsoup4 pdfplumber
# =========================================================================

import os
import re
import csv
import json
import time
import logging
import argparse
import io
import sys
from pathlib import Path
from collections import deque, defaultdict
from dataclasses import dataclass, field, asdict

# 确保 Windows 终端 UTF-8 输出 (仅在直接运行时生效，被 import 时跳过)
if sys.platform == 'win32' and __name__ == '__main__':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

# =========================================================================
# 配置
# =========================================================================
SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR.parent / 'data'
PDF_DOWNLOAD_DIR = SCRIPT_DIR / 'tesa_tds_pdfs'  # 下载的 PDF 存放目录
REPORT_OUTPUT = SCRIPT_DIR / 'tesa_scraped_report.json'  # 爬取结果的中间 JSON

# 德莎产品页有两种 URL 格式：
#   /industry/tesa-75405.html (常见)
#   /industry/66186.html      (少数)
BASE_URLS = [
    "https://www.tesa.com/zh-cn/industry/tesa-{model}.html",
    "https://www.tesa.com/zh-cn/industry/{model}.html",
]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
REQUEST_DELAY = 0.2  # 礼貌爬取间隔 (秒)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('tesa_scraper')

# =========================================================================
# 数据类
# =========================================================================
@dataclass
class TesaProduct:
    """一个德莎产品型号的完整数据"""
    default_code: str = ''           # 如 75405
    name: str = ''                   # tesa® 75405
    description: str = ''            # OG description
    variant_thickness: str = ''      # 50um
    variant_color: str = ''          # 黑色
    variant_base_material: str = ''  # 丙烯酸 / PE泡棉
    variant_adhesive_type: str = ''  # 改性丙烯酸
    features: list[str] = field(default_factory=list)       # 产品特点
    applications: list[str] = field(default_factory=list)    # 主要应用
    tds_pdf_url: str = ''            # TDS PDF 下载链接
    tds_pdf_local: str = ''          # 本地 PDF 路径
    related_models: list[str] = field(default_factory=list)  # 关联型号
    source_url: str = ''             # 产品页 URL

    # PDF 中提取的精确参数
    liner_type: str = ''             # 离型纸类型
    liner_thickness: str = ''        # 离型纸厚度
    liner_color: str = ''            # 离型纸颜色
    total_thickness: str = ''        # 总厚度
    available_thicknesses: str = ''  # 可选厚度
    shear_23c: str = ''              # 23°C静态抗剪切力
    shear_40c: str = ''              # 40°C静态抗剪切力
    temp_short: str = ''             # 短期耐高温性
    temp_long: str = ''              # 长期耐高温性
    uv_resistance: str = ''          # 抗老化(UV)
    elongation: str = ''             # 断裂延展率
    tensile_strength: str = ''       # 抗张强度
    bond_strengths: dict = field(default_factory=dict)  # 各表面粘接强度


# =========================================================================
# 系列归类规则
# =========================================================================
# 前缀 -> (series_xml_id, series_name, base_series_info)
SERIES_PREFIX_MAP: dict[str, tuple[str, str]] = {
    '626': ('catalog_tesa_6262x', '6262x'),
    '628': ('catalog_tesa_628xx', '628xx'),
    '666': ('catalog_tesa_666xx', '666xx'),
    '668': ('catalog_tesa_668xx', '668xx'),
    '754': ('catalog_tesa_754xx', '754xx/756xx'),
    '756': ('catalog_tesa_754xx', '754xx/756xx'),
    '757': ('catalog_tesa_757xx', '757xx'),
    '758': ('catalog_tesa_758xx', '758xx'),
    '759': ('catalog_tesa_759xx', '759xx'),
    '751': ('catalog_tesa_751xx', '751xx'),
    '761': ('catalog_tesa_761xx', '761xx'),
    '471': ('catalog_tesa_471x', '471x'),
    '473': ('catalog_tesa_473x', '473x'),
    '610': ('catalog_tesa_610xx', '610xx'),
    '661': ('catalog_tesa_661xx', '661xx'),
}


def model_to_series(model: str) -> tuple[str, str]:
    """将具体型号映射回系列 (series_xml_id, series_name)"""
    for prefix, (xml_id, name) in SERIES_PREFIX_MAP.items():
        if model.startswith(prefix):
            return xml_id, name
    # 新系列：自动生成
    prefix3 = model[:3]
    return f'catalog_tesa_{prefix3}xx', f'{prefix3}xx'


# =========================================================================
# HTML 爬虫
# =========================================================================
def scrape_product_page(model: str) -> TesaProduct | None:
    """爬取单个产品页面，返回结构化数据（自动尝试多种 URL 格式）"""
    if requests is None or BeautifulSoup is None:
        logger.error("需要安装 requests 和 beautifulsoup4: pip install requests beautifulsoup4")
        return None

    resp = None
    url = ''
    for url_template in BASE_URLS:
        url = url_template.format(model=model)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                break
        except requests.RequestException:
            continue

    if resp is None or resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')
    product = TesaProduct(default_code=str(model), source_url=url)

    # 1. 标题
    h1 = soup.find('h1')
    product.name = h1.get_text(strip=True) if h1 else f'tesa® {model}'

    # 2. OG Description (含厚度+类型关键词)
    og = soup.find('meta', property='og:description')
    product.description = og['content'].strip() if og and og.get('content') else ''

    # 3. 从描述提取厚度和颜色
    _extract_thickness_color_from_desc(product)

    # 4. 提取 产品特点 / 主要应用
    _extract_features_applications(soup, product)

    # 5. TDS PDF 链接
    pdf_link = soup.find('a', href=re.compile(r'/files/download/'))
    if pdf_link:
        href = pdf_link.get('href', '')
        if not href.startswith('http'):
            href = 'https://www.tesa.com' + href
        product.tds_pdf_url = href

    # 6. 关联产品型号 (用于 BFS 发现)
    #    匹配两种 URL: /industry/tesa-62625.html 和 /industry/66186.html
    for a in soup.find_all('a', href=re.compile(r'/industry/(?:tesa-)?\d+')):
        m = re.search(r'/industry/(?:tesa-)?(\d{4,6})', a['href'])
        if m and m.group(1) != model:
            rel_model = m.group(1)
            if rel_model not in product.related_models:
                product.related_models.append(rel_model)

    return product


def _extract_thickness_color_from_desc(product: TesaProduct):
    """从 description 提取厚度和颜色"""
    desc = product.description

    # 厚度：匹配 50μm, 250 µm, 100um 等
    th_match = re.search(r'(\d+)\s*[μµu]m', desc, re.IGNORECASE)
    if th_match:
        product.variant_thickness = f'{th_match.group(1)}um'

    # 颜色
    color_map = {
        '黑色': '黑色', '白色': '白色', '透明': '透明',
        '黑': '黑色', '白': '白色',
    }
    for keyword, color in color_map.items():
        if keyword in desc:
            product.variant_color = color
            break

    # 基材
    material_keywords = [
        ('丙烯酸泡棉', '丙烯酸'), ('PE泡棉', 'PE泡棉'), ('PET', 'PET'),
        ('PU', 'PU'), ('PI', 'PI'), ('泡棉', '泡棉'),
    ]
    for keyword, material in material_keywords:
        if keyword in desc:
            product.variant_base_material = material
            break


def _extract_features_applications(soup: BeautifulSoup, product: TesaProduct):
    """从 HTML 的 h3 > ul 提取特点和应用"""
    for h3 in soup.find_all('h3'):
        title = h3.get_text(strip=True)
        # 查找紧接其后的 <ul>
        ul = h3.find_next_sibling('ul')
        if not ul:
            continue
        items = [li.get_text(strip=True) for li in ul.find_all('li') if li.get_text(strip=True)]

        if '特点' in title:
            product.features = items
        elif '应用' in title:
            product.applications = items


# =========================================================================
# BFS 广度优先爬取
# =========================================================================
def bfs_crawl(seed_models: list[str], max_count: int = 500) -> list[TesaProduct]:
    """BFS 广度优先爬取所有关联产品"""
    visited: set[str] = set()
    queue: deque[str] = deque(seed_models)
    results: list[TesaProduct] = []
    skip_count = 0

    while queue and len(results) < max_count:
        model = queue.popleft()
        if model in visited:
            continue
        visited.add(model)

        logger.info(f"[✅{len(results)} ❌{skip_count} 队列:{len(queue)}] 爬取 tesa-{model} ...")
        product = scrape_product_page(model)

        if product:
            results.append(product)
            desc_preview = product.description[:40] if product.description else product.name
            logger.info(f"  ✅ {desc_preview}")
            # 将关联型号加入队列
            new_found = 0
            for rel in product.related_models:
                if rel not in visited:
                    queue.append(rel)
                    new_found += 1
            if new_found:
                logger.info(f"  🔗 发现 {new_found} 个新关联型号")
        else:
            skip_count += 1
            logger.debug(f"  ❌ 跳过 (404)")

        time.sleep(REQUEST_DELAY)

    logger.info(f"\n🎉 网页爬取完成: 成功 {len(results)} 个, 跳过 {skip_count} 个, 共访问 {len(visited)} 个。")
    return results


# =========================================================================
# PDF 下载器
# =========================================================================
def download_pdfs(products: list[TesaProduct]):
    """批量下载 TDS PDF"""
    PDF_DOWNLOAD_DIR.mkdir(exist_ok=True)
    downloaded = 0

    for product in products:
        if not product.tds_pdf_url:
            continue

        pdf_filename = f"tesa_{product.default_code}_tds.pdf"
        pdf_path = PDF_DOWNLOAD_DIR / pdf_filename

        if pdf_path.exists():
            product.tds_pdf_local = str(pdf_path)
            logger.debug(f"  已存在，跳过: {pdf_filename}")
            continue

        try:
            logger.info(f"  📥 下载 PDF: tesa-{product.default_code} ...")
            resp = requests.get(product.tds_pdf_url, headers=HEADERS, timeout=30)
            if resp.status_code == 200 and resp.headers.get('content-type', '').startswith('application/pdf'):
                pdf_path.write_bytes(resp.content)
                product.tds_pdf_local = str(pdf_path)
                downloaded += 1
                time.sleep(1)
            else:
                logger.warning(f"  ⚠ PDF 下载失败: HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"  ⚠ PDF 下载出错: {e}")

    logger.info(f"📥 PDF 下载完成，新下载 {downloaded} 个。")


# =========================================================================
# PDF 解析器 (核心)
# =========================================================================
def parse_tds_pdf(pdf_path: str) -> TesaProduct | None:
    """
    解析单个德莎 TDS PDF 文件，提取全部结构化参数。
    支持：
      - 本地已有文件
      - 从网站下载的文件
    """
    if pdfplumber is None:
        logger.error("需要安装 pdfplumber: pip install pdfplumber")
        return None

    if not os.path.exists(pdf_path):
        logger.warning(f"PDF 文件不存在: {pdf_path}")
        return None

    try:
        full_text = ''
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + '\n'
    except Exception as e:
        logger.error(f"PDF 解析失败 {pdf_path}: {e}")
        return None

    if not full_text.strip():
        logger.warning(f"PDF 内容为空: {pdf_path}")
        return None

    product = TesaProduct(tds_pdf_local=pdf_path)

    # 1. 提取型号
    model_match = re.search(r'tesa[®\s]*\s*(\d{4,6})', full_text)
    if model_match:
        product.default_code = model_match.group(1)
        product.name = f'tesa® {product.default_code}'
    else:
        # 尝试从文件名提取
        fname = os.path.basename(pdf_path)
        m = re.search(r'(\d{4,6})', fname)
        if m:
            product.default_code = m.group(1)
            product.name = f'tesa® {product.default_code}'
        else:
            logger.warning(f"无法从 PDF 提取型号: {pdf_path}")
            return None

    # 2. 提取描述 (第一行含 µm 的描述)
    desc_match = re.search(
        r'(\d+\s*[μµu]m\s*[^\n]+)',
        full_text, re.IGNORECASE
    )
    if desc_match:
        product.description = desc_match.group(1).strip()

    # 3. 厚度和颜色
    _extract_thickness_color_from_desc(product)
    # 如果描述没找到，从"总厚度"行提取
    total_th = re.search(r'总厚度\s+(\d+)\s*[μµu]m', full_text, re.IGNORECASE)
    if total_th:
        product.total_thickness = f'{total_th.group(1)}um'
        if not product.variant_thickness:
            product.variant_thickness = product.total_thickness

    # 4. 产品结构区块解析
    _parse_product_structure(full_text, product)

    # 5. 属性/性能值
    _parse_properties(full_text, product)

    # 6. 粘接强度
    _parse_bond_strengths(full_text, product)

    # 7. 产品系列 - 可选厚度
    thickness_options = re.search(r'可选厚度\s+(.+)', full_text)
    if thickness_options:
        product.available_thicknesses = thickness_options.group(1).strip()

    # 8. 特点和应用 (从 PDF 文本)
    _parse_features_applications_from_text(full_text, product)

    return product


def _parse_product_structure(text: str, product: TesaProduct):
    """解析产品结构区块"""
    # 基材
    base_mat = re.search(r'基材\s+([^\s·]+(?:\s*[^\s·]+)*?)(?:\s+·|\s*$)', text, re.MULTILINE)
    if base_mat:
        val = base_mat.group(1).strip()
        # 清理特殊字符
        val = re.sub(r'[（\(](聚[^）\)]+)[）\)]', '', val).strip()
        if val and not product.variant_base_material:
            product.variant_base_material = val

    # 胶粘剂类型
    adhesive = re.search(r'㬵粘剂类型\s+(.+?)(?:\s+·|\s*$)', text, re.MULTILINE)
    if not adhesive:
        adhesive = re.search(r'胶粘剂类型\s+(.+?)(?:\s+·|\s*$)', text, re.MULTILINE)
    if adhesive:
        product.variant_adhesive_type = adhesive.group(1).strip()

    # 颜色 (从产品结构行)
    color = re.search(r'颜⾊\s+([^\s·]+)', text)
    if not color:
        color = re.search(r'颜色\s+([^\s·]+)', text)
    if color and not product.variant_color:
        product.variant_color = color.group(1).strip()

    # 离型纸
    liner_type = re.search(r'离型纸类型\s+(.+?)(?:\s+·|\s*$)', text, re.MULTILINE)
    if liner_type:
        product.liner_type = liner_type.group(1).strip()

    liner_th = re.search(r'离型纸厚度\s+(\d+)\s*[μµu]m', text, re.IGNORECASE)
    if liner_th:
        product.liner_thickness = f'{liner_th.group(1)}um'

    liner_color = re.search(r'离型纸颜⾊\s+(\S+)', text)
    if not liner_color:
        liner_color = re.search(r'离型纸颜色\s+(\S+)', text)
    if liner_color:
        product.liner_color = liner_color.group(1).strip()


def _parse_properties(text: str, product: TesaProduct):
    """解析属性/性能值"""
    # 23°C 静态抗剪切力
    m = re.search(r'23°?C\s*静态抗剪切⼒?\s+(\S+)', text)
    if m:
        product.shear_23c = m.group(1)

    m = re.search(r'40°?C\s*静态抗剪切⼒?\s+(\S+)', text)
    if m:
        product.shear_40c = m.group(1)

    # 短期/长期耐温
    m = re.search(r'短期耐⾼?温性\s+(\d+)\s*°C', text)
    if not m:
        m = re.search(r'短期耐高温性\s+(\d+)\s*°C', text)
    if m:
        product.temp_short = f'{m.group(1)}°C'

    m = re.search(r'[⻓长]期耐⾼?温性\s+(\d+)\s*°C', text)
    if not m:
        m = re.search(r'长期耐高温性\s+(\d+)\s*°C', text)
    if m:
        product.temp_long = f'{m.group(1)}°C'

    # UV 抗老化
    m = re.search(r'抗⽼化[（(]UV[）)]\s+(\S+)', text)
    if not m:
        m = re.search(r'抗老化[（(]UV[）)]\s+(\S+)', text)
    if m:
        product.uv_resistance = m.group(1)

    # 断裂延展率
    m = re.search(r'断裂延展率\s+([\d.]+)\s*%', text)
    if m:
        product.elongation = f'{m.group(1)}%'

    # 抗张强度
    m = re.search(r'抗张强度\s+([\d.]+)\s*N/cm', text)
    if m:
        product.tensile_strength = f'{m.group(1)} N/cm'


def _parse_bond_strengths(text: str, product: TesaProduct):
    """解析各表面粘接强度"""
    # 匹配如：铝表面粘接强度（初始） 5.5 N/cm
    pattern = re.compile(
        r'(\S+)表⾯?粘接强度[（(]([^）)]+)[）)]\s+([\d.]+)\s*N/cm'
    )
    for m in pattern.finditer(text):
        surface = m.group(1).replace('⾯', '面')
        condition = m.group(2)
        value = m.group(3)
        key = f'{surface}({condition})'
        product.bond_strengths[key] = f'{value} N/cm'

    # 兼容标准字符
    if not product.bond_strengths:
        pattern2 = re.compile(
            r'(\S+)表面粘接强度[（(]([^）)]+)[）)]\s+([\d.]+)\s*N/cm'
        )
        for m in pattern2.finditer(text):
            key = f'{m.group(1)}({m.group(2)})'
            product.bond_strengths[key] = f'{m.group(3)} N/cm'


def _parse_features_applications_from_text(text: str, product: TesaProduct):
    """从 PDF 纯文本提取特点和应用列表"""
    if not product.features:
        features_section = re.search(r'特点\s*\n((?:\s*·.+\n?)+)', text)
        if features_section:
            product.features = [
                line.strip().lstrip('·').strip()
                for line in features_section.group(1).split('\n')
                if line.strip().startswith('·')
            ]

    if not product.applications:
        app_section = re.search(r'应⽤\s*\n((?:\s*·.+\n?)+)', text)
        if not app_section:
            app_section = re.search(r'应用\s*\n((?:\s*·.+\n?)+)', text)
        if app_section:
            product.applications = [
                line.strip().lstrip('·').strip()
                for line in app_section.group(1).split('\n')
                if line.strip().startswith('·')
            ]


# =========================================================================
# 合并 Web + PDF 数据
# =========================================================================
def merge_web_and_pdf(web_product: TesaProduct, pdf_product: TesaProduct) -> TesaProduct:
    """将网页数据与 PDF 数据合并，PDF 优先"""
    merged = web_product

    # PDF 中提取的精确参数覆盖网页的
    if pdf_product.variant_base_material:
        merged.variant_base_material = pdf_product.variant_base_material
    if pdf_product.variant_adhesive_type:
        merged.variant_adhesive_type = pdf_product.variant_adhesive_type
    if pdf_product.variant_color:
        merged.variant_color = pdf_product.variant_color
    if pdf_product.total_thickness:
        merged.total_thickness = pdf_product.total_thickness
    if pdf_product.variant_thickness and not merged.variant_thickness:
        merged.variant_thickness = pdf_product.variant_thickness

    # 性能参数直接从 PDF
    for attr in ('liner_type', 'liner_thickness', 'liner_color',
                 'available_thicknesses', 'shear_23c', 'shear_40c',
                 'temp_short', 'temp_long', 'uv_resistance',
                 'elongation', 'tensile_strength'):
        pdf_val = getattr(pdf_product, attr, '')
        if pdf_val:
            setattr(merged, attr, pdf_val)

    if pdf_product.bond_strengths:
        merged.bond_strengths = pdf_product.bond_strengths

    # 补充特点/应用
    if pdf_product.features and not merged.features:
        merged.features = pdf_product.features
    if pdf_product.applications and not merged.applications:
        merged.applications = pdf_product.applications

    return merged


# =========================================================================
# 批量 PDF 解析 (支持用户本地文件)
# =========================================================================
def parse_local_pdfs(pdf_dir: str | Path) -> list[TesaProduct]:
    """批量解析文件夹中的所有 PDF 文件"""
    pdf_dir = Path(pdf_dir)
    if not pdf_dir.exists():
        logger.error(f"PDF 目录不存在: {pdf_dir}")
        return []

    pdf_files = sorted(pdf_dir.glob('*.pdf'))
    logger.info(f"📂 在 {pdf_dir} 中找到 {len(pdf_files)} 个 PDF 文件")

    results: list[TesaProduct] = []
    for pdf_file in pdf_files:
        logger.info(f"  📄 解析: {pdf_file.name} ...")
        product = parse_tds_pdf(str(pdf_file))
        if product:
            results.append(product)
            logger.info(f"     ✅ {product.name} | 厚度={product.variant_thickness} "
                        f"| 基材={product.variant_base_material} | 胶系={product.variant_adhesive_type}")
        else:
            logger.warning(f"     ⚠️ 解析失败或无效")

    logger.info(f"\n📄 PDF 解析完成，成功解析 {len(results)} 个产品。")
    return results


# =========================================================================
# 输出到 CSV (集成到既有流水线)
# =========================================================================
def _ensure_csv_schema(csv_path: Path, required_headers: list[str], csv_label: str) -> list[str]:
    """
    确保 CSV 文件存在且包含 required_headers。
    - 若文件不存在：创建并写入 required_headers
    - 若文件存在但缺字段：自动扩展表头并保留历史数据
    - 字段顺序策略：保留现有顺序 + 新字段追加到末尾
    返回最终可用的表头列表。
    """
    if not csv_path.exists():
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(required_headers)
        logger.info(f"  🧱 初始化 {csv_label}: 创建文件并写入表头")
        return required_headers[:]

    with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        existing_headers = list(reader.fieldnames or [])
        existing_rows = list(reader)

    if not existing_headers:
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(required_headers)
        logger.warning(f"  ⚠️ {csv_label} 无有效表头，已按默认表头重建")
        return required_headers[:]

    missing_headers = [h for h in required_headers if h not in existing_headers]
    if not missing_headers:
        return existing_headers

    final_headers = existing_headers + missing_headers
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=final_headers)
        writer.writeheader()
        writer.writerows(existing_rows)

    logger.info(f"  🔧 检测到 {csv_label} 缺失字段: {missing_headers}")
    logger.info(f"  ✅ 已自动扩展 {csv_label} 表头并保留 {len(existing_rows)} 条历史记录")
    return final_headers


def export_to_csv(products: list[TesaProduct], update_series: bool = True):
    """
    将产品数据输出到 series.csv 和 variants.csv。
    - 增量追加：已有的不覆盖
    - 自动发现新系列
    """
    series_csv = SCRIPT_DIR / 'series.csv'
    variants_csv = SCRIPT_DIR / 'variants.csv'

    series_headers = [
        'brand_id_xml', 'categ_id_xml', 'series_xml_id', 'name',
        'series_name', 'catalog_base_material', 'catalog_adhesive_type',
        'catalog_characteristics', 'catalog_features', 'catalog_applications'
    ]
    variant_headers = [
        'series_xml_id', 'default_code', 'variant_thickness',
        'variant_color', 'variant_adhesive_type', 'variant_base_material',
        'variant_peel_strength', 'variant_adhesive_std', 'variant_base_material_std',
        'variant_color_std', 'variant_fire_rating', 'variant_holding_power',
        'variant_pe_peel', 'variant_sus_peel', 'variant_thickness_std',
    ]

    # ---------- 0. 确保 CSV 结构可用（自动扩展缺失字段） ----------
    final_series_headers = _ensure_csv_schema(series_csv, series_headers, 'series.csv')
    final_variant_headers = _ensure_csv_schema(variants_csv, variant_headers, 'variants.csv')

    # ---------- 1. 读取现有 CSV ----------
    existing_series: dict[str, dict] = {}
    existing_variants: set[str] = set()

    if series_csv.exists():
        with open(series_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid = row.get('series_xml_id', '').strip()
                if sid:
                    existing_series[sid] = row

    if variants_csv.exists():
        with open(variants_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get('default_code', '').strip()
                if code:
                    existing_variants.add(code)

    # ---------- 2. 按系列归类 ----------
    series_products: dict[str, list[TesaProduct]] = defaultdict(list)
    for p in products:
        series_xml_id, _ = model_to_series(p.default_code)
        series_products[series_xml_id].append(p)

    # ---------- 3. 追加新系列到 series.csv ----------
    new_series_count = 0
    if update_series:
        with open(series_csv, 'a', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=final_series_headers)
            for series_id, prods in series_products.items():
                if series_id in existing_series:
                    continue
                _, series_name = model_to_series(prods[0].default_code)
                # 取第一个产品的参数作为系列代表
                rep = prods[0]

                features_text = '；'.join(rep.features) if rep.features else rep.description
                apps_text = '、'.join(rep.applications) if rep.applications else ''
                characteristics = ''
                if rep.features:
                    # 从特点取前2个关键词作为特性标签
                    short_features = [f[:6] for f in rep.features[:2]]
                    characteristics = '，'.join(short_features)

                writer.writerow({
                    'brand_id_xml': 'brand_tesa',
                    'categ_id_xml': 'category_tape_foam',
                    'series_xml_id': series_id,
                    'name': f'tesa® {series_name} 胶带',
                    'series_name': series_name,
                    'catalog_base_material': rep.variant_base_material,
                    'catalog_adhesive_type': rep.variant_adhesive_type,
                    'catalog_characteristics': characteristics,
                    'catalog_features': features_text,
                    'catalog_applications': apps_text,
                })
                new_series_count += 1
                logger.info(f"  📝 新系列: {series_id} ({series_name})")

    # ---------- 4. 追加新变体到 variants.csv ----------
    new_variant_count = 0
    with open(variants_csv, 'a', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=final_variant_headers)
        for p in products:
            if p.default_code in existing_variants:
                continue
            series_xml_id, _ = model_to_series(p.default_code)

            # 构造粘接强度的摘要 (用于 variant_peel_strength)
            peel_summary = ''
            if p.bond_strengths:
                # 模糊匹配钢面初始值 (兼容不同 LLM 的命名风格)
                for key, val in p.bond_strengths.items():
                    if '钢' in key and '初始' in key:
                        peel_summary = val
                        break
                if not peel_summary:
                    # 取第一个
                    peel_summary = list(p.bond_strengths.values())[0]

            writer.writerow({
                'series_xml_id': series_xml_id,
                'default_code': p.default_code,
                'variant_thickness': p.variant_thickness,
                'variant_color': p.variant_color or '黑色',
                'variant_adhesive_type': p.variant_adhesive_type,
                'variant_base_material': p.variant_base_material,
                'variant_peel_strength': peel_summary,
                'variant_adhesive_std': p.variant_adhesive_type,
                'variant_base_material_std': p.variant_base_material,
                'variant_color_std': p.variant_color or '黑色',
                'variant_fire_rating': 'none',
                'variant_holding_power': '',
                'variant_pe_peel': '',
                'variant_sus_peel': '',
                'variant_thickness_std': p.variant_thickness,
            })
            new_variant_count += 1

    logger.info(f"\n📊 CSV 写入完成:")
    logger.info(f"   新增系列: {new_series_count}")
    logger.info(f"   新增变体: {new_variant_count}")
    logger.info(f"   跳过已有: {len(products) - new_variant_count}")


# =========================================================================
# 报告输出
# =========================================================================
def save_report(products: list[TesaProduct]):
    """保存中间结果为 JSON (方便调试和二次处理)"""
    report = []
    for p in products:
        d = asdict(p)
        report.append(d)

    with open(REPORT_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"💾 详细报告已保存: {REPORT_OUTPUT}")


def print_summary(products: list[TesaProduct]):
    """打印最终的数据质量摘要"""
    total = len(products)
    has_thickness = sum(1 for p in products if p.variant_thickness)
    has_material = sum(1 for p in products if p.variant_base_material)
    has_adhesive = sum(1 for p in products if p.variant_adhesive_type)
    has_color = sum(1 for p in products if p.variant_color)
    has_features = sum(1 for p in products if p.features)
    has_pdf = sum(1 for p in products if p.tds_pdf_local)
    has_bonds = sum(1 for p in products if p.bond_strengths)

    # 按系列统计
    series_count: dict[str, int] = defaultdict(int)
    for p in products:
        s_id, _ = model_to_series(p.default_code)
        series_count[s_id] += 1

    print(f"\n{'='*60}")
    print(f"📊 数据质量摘要")
    print(f"{'='*60}")
    print(f"  总产品数:      {total}")
    print(f"  有厚度:        {has_thickness}/{total} ({has_thickness/total*100:.0f}%)" if total else "")
    print(f"  有基材:        {has_material}/{total} ({has_material/total*100:.0f}%)" if total else "")
    print(f"  有胶系:        {has_adhesive}/{total} ({has_adhesive/total*100:.0f}%)" if total else "")
    print(f"  有颜色:        {has_color}/{total} ({has_color/total*100:.0f}%)" if total else "")
    print(f"  有产品特点:    {has_features}/{total} ({has_features/total*100:.0f}%)" if total else "")
    print(f"  有 PDF:        {has_pdf}/{total} ({has_pdf/total*100:.0f}%)" if total else "")
    print(f"  有粘接强度:    {has_bonds}/{total} ({has_bonds/total*100:.0f}%)" if total else "")
    print(f"\n  按系列分布:")
    for s_id, count in sorted(series_count.items()):
        print(f"    {s_id}: {count} 个型号")
    print(f"{'='*60}\n")


# =========================================================================
# CLI 入口
# =========================================================================
def main():
    parser = argparse.ArgumentParser(
        description='德莎 (Tesa) 产品数据采集工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 从官网爬取 (BFS 自动发现新型号)
  python scrape_tesa.py --mode web

  # 只解析本地 PDF 文件夹 (如你手动下载的 TDS 文件)
  python scrape_tesa.py --mode pdf --pdf-dir ./my_pdfs

  # 先爬网页，下载 PDF, 再解析 PDF（最完整的模式）
  python scrape_tesa.py --mode all

  # 🤖 用 LLM AI 解析任意品牌的 TDS PDF (推荐！)
  python scrape_tesa.py --mode llm --pdf-dir ./任意品牌TDS

  # 限制爬取数量 (测试用)
  python scrape_tesa.py --mode web --max 10

  # 添加额外种子型号
  python scrape_tesa.py --mode web --seeds 61055,66186
        """
    )
    parser.add_argument('--mode', choices=['web', 'pdf', 'all', 'llm'], default='all',
                        help='运行模式: web=只爬网页, pdf=正则解析本地PDF, all=全部, llm=AI解析任意PDF')
    parser.add_argument('--pdf-dir', type=str, default=str(PDF_DOWNLOAD_DIR),
                        help=f'PDF 文件目录 (默认: {PDF_DOWNLOAD_DIR})')
    parser.add_argument('--max', type=int, default=500,
                        help='最大爬取数量 (默认 500)')
    parser.add_argument('--seeds', type=str, default='',
                        help='额外种子型号，用逗号分隔 (如: 61055,66186)')
    parser.add_argument('--no-csv', action='store_true',
                        help='不写入 CSV (只生成 JSON 报告)')
    parser.add_argument('--no-download-pdf', action='store_true',
                        help='不下载 PDF (只解析网页)')
    parser.add_argument('--llm-delay', type=float, default=2.0,
                        help='LLM 模式: 请求间隔秒数 (默认 2.0)')
    parser.add_argument('--provider', type=str, default='deepseek',
                        choices=['deepseek', 'qwen', 'zhipu', 'gemini'],
                        help='LLM 提供商 (默认 deepseek)')
    parser.add_argument('--force-rewrite', action='store_true',
                        help='强制用新数据覆盖旧 CSV (LLM 模式推荐)')

    args = parser.parse_args()

    # 构建种子型号列表 (来自现有 variants.csv 的所有已知型号)
    seed_models = []
    variants_csv = SCRIPT_DIR / 'variants.csv'
    if variants_csv.exists():
        with open(variants_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get('default_code', '').strip()
                if code:
                    seed_models.append(code)

    # 如果没有已知型号，用默认种子
    if not seed_models:
        seed_models = ['75405', '62625', '66824', '75120', '75710',
                       '75920', '75805', '76105', '4718', '4738']

    # 追加用户指定的额外种子
    if args.seeds:
        extra = [s.strip() for s in args.seeds.split(',') if s.strip()]
        seed_models.extend(extra)

    # 去重
    seed_models = list(dict.fromkeys(seed_models))

    all_products: list[TesaProduct] = []

    # ===== STAGE 1: 网页爬取 =====
    if args.mode in ('web', 'all'):
        logger.info(f"🌐 开始网页爬取 (种子型号 {len(seed_models)} 个, 最大 {args.max}) ...")
        web_products = bfs_crawl(seed_models, max_count=args.max)
        all_products = web_products

        # 下载 PDF
        if not args.no_download_pdf:
            logger.info(f"\n📥 开始下载 TDS PDF 文件 ...")
            download_pdfs(all_products)

    # ===== STAGE 2: PDF 解析 (正则 或 LLM) =====
    if args.mode in ('pdf', 'all', 'llm'):
        pdf_dir = Path(args.pdf_dir)
        if pdf_dir.exists() and list(pdf_dir.glob('*.pdf')):
            if args.mode == 'llm':
                # ====== LLM AI 模式 ======
                logger.info(f"\n🤖 LLM AI 模式: 解析 {pdf_dir} 中的 PDF ...")
                # --force-rewrite: 删除旧 CSV，重新写入
                if args.force_rewrite:
                    for old_csv in [SCRIPT_DIR / 'series.csv', SCRIPT_DIR / 'variants.csv']:
                        if old_csv.exists():
                            old_csv.unlink()
                            logger.info(f"  🗑️ 已删除旧文件: {old_csv.name}")
                from llm_tds_parser import llm_parse_batch, llm_result_to_tesa_product
                llm_results = llm_parse_batch(str(pdf_dir), delay=args.llm_delay,
                                              provider=args.provider)
                all_products = [llm_result_to_tesa_product(d) for d in llm_results]
            else:
                # ====== 正则模式 ======
                logger.info(f"\n📄 开始解析本地 PDF 文件: {pdf_dir} ...")
                pdf_products = parse_local_pdfs(pdf_dir)

                if args.mode == 'all' and all_products:
                    # 合并 web + pdf 数据
                    pdf_map = {p.default_code: p for p in pdf_products}
                    for i, wp in enumerate(all_products):
                        if wp.default_code in pdf_map:
                            all_products[i] = merge_web_and_pdf(wp, pdf_map[wp.default_code])
                    # 添加 PDF 中有但网页没爬到的产品
                    web_codes = {p.default_code for p in all_products}
                    for pp in pdf_products:
                        if pp.default_code not in web_codes:
                            all_products.append(pp)
                elif args.mode == 'pdf':
                    all_products = pdf_products
        else:
            logger.info(f"📂 PDF 目录 {pdf_dir} 不存在或为空")
            if args.mode in ('pdf', 'llm'):
                logger.error("pdf/llm 模式但没有 PDF 文件可解析！")
                return

    if not all_products:
        logger.warning("⚠️ 没有采集到任何产品数据。")
        return

    # ===== STAGE 3: 输出 =====
    print_summary(all_products)
    save_report(all_products)

    if not args.no_csv:
        export_to_csv(all_products)
        logger.info(f"\n✅ 全部完成！接下来运行:")
        logger.info(f"   python generate_catalog.py   # 生成 XML + JSON")
        logger.info(f"   然后在 Odoo 中升级 diecut 模块即可。")


if __name__ == '__main__':
    main()
