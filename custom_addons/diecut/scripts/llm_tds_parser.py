# scripts/llm_tds_parser.py
# =========================================================================
# 通用 TDS PDF 解析器 (基于 LLM)
# 支持多个 LLM 提供商:
#   - DeepSeek (推荐, 最便宜, 中文最强)
#   - 通义千问 Qwen (阿里云)
#   - 智谱 GLM (免费)
#   - Google Gemini
#
# 使用方式:
#   python llm_tds_parser.py ./pdfs                      # 默认 DeepSeek
#   python llm_tds_parser.py ./pdfs --provider qwen      # 通义千问
#   python llm_tds_parser.py ./pdfs --provider gemini    # Google Gemini
#   python scrape_tesa.py --mode llm --pdf-dir ./pdfs    # 集成模式
# =========================================================================

import os
import re
import json
import logging
import sys
import io
import time
from pathlib import Path

if sys.platform == 'win32' and __name__ == '__main__':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

logger = logging.getLogger('tds_llm_parser')

# =========================================================================
# LLM 提供商配置
# =========================================================================
PROVIDERS = {
    'deepseek': {
        'name': 'DeepSeek',
        'base_url': 'https://api.deepseek.com',
        'model': 'deepseek-chat',
        'env_key': 'DEEPSEEK_API_KEY',
        'price_info': '¥1/百万 input token, ¥2/百万 output token',
        'signup_url': 'https://platform.deepseek.com/api_keys',
    },
    'qwen': {
        'name': '通义千问 (Qwen)',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'model': 'qwen-plus',
        'env_key': 'QWEN_API_KEY',
        'price_info': '¥0.8/百万 input token',
        'signup_url': 'https://dashscope.console.aliyun.com/apiKey',
    },
    'zhipu': {
        'name': '智谱 GLM',
        'base_url': 'https://open.bigmodel.cn/api/paas/v4',
        'model': 'glm-4-flash',
        'env_key': 'ZHIPU_API_KEY',
        'price_info': '免费 (glm-4-flash)',
        'signup_url': 'https://open.bigmodel.cn/usercenter/apikeys',
    },
    'gemini': {
        'name': 'Google Gemini',
        'base_url': None,  # 使用 google-generativeai SDK
        'model': 'gemini-2.0-flash',
        'env_key': 'GEMINI_API_KEY',
        'price_info': '免费配额 1000次/天; 付费 $0.10/百万 token',
        'signup_url': 'https://aistudio.google.com/apikey',
    },
}

# 默认提供商
DEFAULT_PROVIDER = 'deepseek'

# =========================================================================
# 提取 Prompt (统一，所有 LLM 共用)
# =========================================================================
EXTRACTION_PROMPT = """你是一个专业的胶带/胶粘材料技术工程师。请从以下 TDS (Technical Data Sheet / 产品信息 / 技术数据表) 文档中，提取所有结构化的技术参数。

请严格按以下 JSON 格式输出（不要添加任何额外字段、不要输出 markdown 代码块标记、只输出纯 JSON）：

{{
  "product_code": "产品型号编码，如 75405、6965、4965、不含品牌前缀",
  "brand": "品牌名，如 tesa、3M、Nitto、Sidike",
  "product_name": "产品的完整名称",
  "description": "产品简短描述（一句话概括用途和特性）",
  "total_thickness": "总厚度，含单位如 50μm、0.05mm",
  "base_material": "基材类型，如 PE泡棉、PET、丙烯酸、PI",
  "adhesive_type": "胶粘剂类型，如 改性丙烯酸、合成橡胶、硅胶",
  "color": "颜色，如 黑色、白色、透明",
  "liner_type": "离型纸/衬纸类型",
  "liner_thickness": "离型纸厚度",
  "available_thicknesses": "可选的其他厚度规格（如有），用逗号分隔",
  "peel_strength": "180°剥离强度，含单位和测试条件",
  "holding_power": "保持力/静态剪切力",
  "temp_resistance_short": "短期耐温上限，如 140°C",
  "temp_resistance_long": "长期耐温上限，如 90°C",
  "elongation": "断裂延展率，如 340%",
  "tensile_strength": "抗张强度，含单位",
  "uv_resistance": "UV/抗老化性能",
  "density": "密度（如有），含单位",
  "fire_rating": "防火等级（如有），如 UL94 V-0",
  "features": ["产品特点1", "产品特点2"],
  "applications": ["应用场景1", "应用场景2"],
  "bond_strengths": {{
    "钢(初始)": "9.1 N/cm",
    "PC(14天后)": "16 N/cm"
  }}
}}

TDS 文档全文内容：
---
{text}
---

重要提示：
1. 所有数值必须保留原始单位（如 µm, N/cm, °C, %, mm）
2. 如果文档中没有某个字段的信息，填空字符串 ""
3. features 和 applications 提取为数组
4. bond_strengths 只包含有实际数据的条目（没有数据不要编造）
5. 原文是什么语言就用什么语言填写（中文文档用中文、英文文档用英文）
6. product_code 只填纯数字/字母型号，不要包含 "tesa®" 等品牌前缀"""


# =========================================================================
# OpenAI 兼容客户端 (DeepSeek / Qwen / 智谱 共用)
# =========================================================================
_openai_client = None
_current_provider_name = None

def _get_openai_client(provider: str = DEFAULT_PROVIDER):
    """初始化 OpenAI 兼容客户端"""
    global _openai_client, _current_provider_name

    if _openai_client is not None and _current_provider_name == provider:
        return _openai_client

    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("请安装 openai: pip install openai")

    cfg = PROVIDERS[provider]
    api_key = os.environ.get(cfg['env_key'], '')
    if not api_key:
        raise ValueError(
            f"未找到 {cfg['env_key']}！\n"
            f"请在 scripts/.env 文件中设置:\n"
            f"  {cfg['env_key']}=你的密钥\n"
            f"获取地址: {cfg['signup_url']}"
        )

    _openai_client = OpenAI(
        api_key=api_key,
        base_url=cfg['base_url'],
    )
    _current_provider_name = provider
    logger.info(f"🤖 已初始化 {cfg['name']} ({cfg['model']})")
    logger.info(f"   价格: {cfg['price_info']}")
    return _openai_client


# =========================================================================
# Gemini 客户端 (单独处理)
# =========================================================================
_gemini_model = None

def _get_gemini_model():
    """延迟初始化 Gemini 模型"""
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model

    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError("请安装 google-generativeai: pip install google-generativeai")

    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError("未找到 GEMINI_API_KEY！")

    genai.configure(api_key=api_key)
    _gemini_model = genai.GenerativeModel("gemini-2.0-flash")
    logger.info("🤖 Gemini 2.0 Flash 模型已初始化")
    return _gemini_model


# =========================================================================
# 核心解析函数
# =========================================================================
def _extract_pdf_text(pdf_path: str) -> str | None:
    """提取 PDF 文本"""
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
        logger.error(f"PDF 读取失败 {pdf_path}: {e}")
        return None

    if not full_text.strip():
        logger.warning(f"PDF 内容为空: {pdf_path}")
        return None

    return full_text


def _call_openai_compatible(text: str, provider: str, max_retries: int = 3) -> dict | None:
    """通过 OpenAI 兼容接口调用 LLM (DeepSeek / Qwen / 智谱)"""
    client = _get_openai_client(provider)
    cfg = PROVIDERS[provider]
    prompt = EXTRACTION_PROMPT.format(text=text[:12000])

    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=cfg['model'],
                messages=[
                    {"role": "system", "content": "你是专业的胶带技术工程师，擅长从 TDS 文档中提取结构化参数。只输出纯 JSON，不要输出任何其他文字。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            raw_text = response.choices[0].message.content.strip()

            # 兜底清理 markdown 代码块
            if raw_text.startswith('```'):
                raw_text = re.sub(r'^```\w*\n?', '', raw_text)
                raw_text = re.sub(r'\n?```$', '', raw_text)

            result = json.loads(raw_text)

            if not result.get('product_code'):
                logger.warning(f"LLM 未提取到 product_code")
                return None

            return result

        except json.JSONDecodeError as e:
            logger.error(f"LLM 返回非法 JSON: {e}")
            return None

        except Exception as e:
            err_str = str(e)
            if '429' in err_str or 'rate' in err_str.lower():
                wait_match = re.search(r'(\d+)\s*s', err_str)
                wait_secs = int(wait_match.group(1)) + 2 if wait_match else 30
                if attempt < max_retries:
                    logger.warning(f"  ⏳ 限流, 等待 {wait_secs}s 后重试 ({attempt}/{max_retries})...")
                    time.sleep(wait_secs)
                    continue
                else:
                    logger.error(f"  ❌ 重试 {max_retries} 次仍失败")
                    return None
            else:
                logger.error(f"LLM 调用失败: {e}")
                return None

    return None


def _call_gemini(text: str, max_retries: int = 3) -> dict | None:
    """通过 Gemini SDK 调用"""
    import google.generativeai as genai

    model = _get_gemini_model()
    prompt = EXTRACTION_PROMPT.format(text=text[:12000])

    for attempt in range(1, max_retries + 1):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )

            raw_text = response.text.strip()
            if raw_text.startswith('```'):
                raw_text = re.sub(r'^```\w*\n?', '', raw_text)
                raw_text = re.sub(r'\n?```$', '', raw_text)

            result = json.loads(raw_text)
            if not result.get('product_code'):
                logger.warning(f"LLM 未提取到 product_code")
                return None
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Gemini 返回非法 JSON: {e}")
            return None

        except Exception as e:
            err_str = str(e)
            if '429' in err_str:
                wait_match = re.search(r'retry in ([\d.]+)s', err_str, re.IGNORECASE)
                if not wait_match:
                    wait_match = re.search(r'seconds:\s*([\d.]+)', err_str)
                wait_secs = float(wait_match.group(1)) + 2 if wait_match else 30.0
                if attempt < max_retries:
                    logger.warning(f"  ⏳ 限流 429, 等待 {wait_secs:.0f}s 后重试 ({attempt}/{max_retries})...")
                    time.sleep(wait_secs)
                    continue
                else:
                    logger.error(f"  ❌ 重试 {max_retries} 次仍失败")
                    return None
            else:
                logger.error(f"Gemini 调用失败: {e}")
                return None

    return None


def llm_parse_tds_pdf(pdf_path: str, provider: str = DEFAULT_PROVIDER) -> dict | None:
    """
    使用 LLM 解析任意品牌的 TDS PDF。
    
    Args:
        pdf_path: PDF 文件路径
        provider: LLM 提供商 (deepseek / qwen / zhipu / gemini)
    
    Returns:
        解析后的字典；失败返回 None
    """
    text = _extract_pdf_text(pdf_path)
    if not text:
        return None

    if provider == 'gemini':
        result = _call_gemini(text)
    else:
        result = _call_openai_compatible(text, provider)

    if result:
        logger.info(f"  ✅ {result.get('brand', '?')} {result['product_code']} | "
                     f"厚度={result.get('total_thickness', '?')} | "
                     f"基材={result.get('base_material', '?')} | "
                     f"胶系={result.get('adhesive_type', '?')}")

    return result


def llm_parse_batch(pdf_dir: str | Path, delay: float = 2.0,
                    provider: str = DEFAULT_PROVIDER) -> list[dict]:
    """
    批量 LLM 解析 PDF 目录。
    
    Args:
        pdf_dir: PDF 文件目录
        delay: 请求间隔（秒）
        provider: LLM 提供商
    """
    pdf_dir = Path(pdf_dir)
    if not pdf_dir.exists():
        logger.error(f"PDF 目录不存在: {pdf_dir}")
        return []

    pdf_files = sorted(pdf_dir.glob('*.pdf'))
    if not pdf_files:
        logger.warning(f"目录 {pdf_dir} 中没有 PDF 文件")
        return []

    cfg = PROVIDERS.get(provider, PROVIDERS[DEFAULT_PROVIDER])
    logger.info(f"🤖 LLM 批量解析: {len(pdf_files)} 个 PDF")
    logger.info(f"   提供商: {cfg['name']} ({cfg['model']})")
    logger.info(f"   价格: {cfg['price_info']}")
    logger.info(f"   请求间隔: {delay}s")

    results: list[dict] = []
    failed = 0

    for i, pdf_file in enumerate(pdf_files, 1):
        logger.info(f"\n[{i}/{len(pdf_files)} ✅{len(results)} ❌{failed}] 📄 {pdf_file.name}")

        data = llm_parse_tds_pdf(str(pdf_file), provider=provider)
        if data:
            data['_source_file'] = pdf_file.name
            results.append(data)
        else:
            failed += 1

        if i < len(pdf_files):
            time.sleep(delay)

    logger.info(f"\n{'='*50}")
    logger.info(f"🤖 LLM 批量解析完成: 成功 {len(results)}, 失败 {failed}")
    logger.info(f"{'='*50}")
    return results


def llm_result_to_tesa_product(data: dict):
    """将 LLM 解析结果转换为 TesaProduct (兼容现有 CSV 流水线)"""
    from scrape_tesa import TesaProduct

    return TesaProduct(
        default_code=str(data.get('product_code', '')),
        name=data.get('product_name', ''),
        description=data.get('description', ''),
        variant_thickness=data.get('total_thickness', ''),
        variant_color=data.get('color', ''),
        variant_base_material=data.get('base_material', ''),
        variant_adhesive_type=data.get('adhesive_type', ''),
        features=data.get('features', []),
        applications=data.get('applications', []),
        tds_pdf_local=data.get('_source_file', ''),
        liner_type=data.get('liner_type', ''),
        liner_thickness=data.get('liner_thickness', ''),
        available_thicknesses=data.get('available_thicknesses', ''),
        shear_23c=data.get('holding_power', ''),
        temp_short=data.get('temp_resistance_short', ''),
        temp_long=data.get('temp_resistance_long', ''),
        uv_resistance=data.get('uv_resistance', ''),
        elongation=data.get('elongation', ''),
        tensile_strength=data.get('tensile_strength', ''),
        bond_strengths=data.get('bond_strengths', {}),
    )


# =========================================================================
# CLI 入口
# =========================================================================
if __name__ == '__main__':
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
    )

    parser = argparse.ArgumentParser(
        description='通用 TDS PDF LLM 解析器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
支持的 LLM 提供商:
  deepseek  - DeepSeek (推荐, ¥1/百万token, 中文最强)
  qwen      - 通义千问 (阿里云, ¥0.8/百万token)
  zhipu     - 智谱 GLM-4-Flash (免费!)
  gemini    - Google Gemini 2.0 Flash

使用示例:
  python llm_tds_parser.py ./pdfs                        # 默认 DeepSeek
  python llm_tds_parser.py ./pdfs --provider qwen        # 用通义千问
  python llm_tds_parser.py ./pdfs --provider zhipu       # 用智谱 (免费)
  python llm_tds_parser.py single.pdf                    # 解析单个文件
        """
    )
    parser.add_argument('pdf_path', help='PDF 文件或目录路径')
    parser.add_argument('--provider', choices=list(PROVIDERS.keys()),
                        default=DEFAULT_PROVIDER,
                        help=f'LLM 提供商 (默认: {DEFAULT_PROVIDER})')
    parser.add_argument('--delay', type=float, default=2.0,
                        help='请求间隔秒数 (默认 2.0)')
    parser.add_argument('--output', type=str, default='llm_parsed_results.json',
                        help='输出 JSON 文件名')
    args = parser.parse_args()

    target = Path(args.pdf_path)

    if target.is_file():
        result = llm_parse_tds_pdf(str(target), provider=args.provider)
        results = [result] if result else []
    elif target.is_dir():
        results = llm_parse_batch(str(target), delay=args.delay, provider=args.provider)
    else:
        print(f"路径不存在: {target}")
        sys.exit(1)

    if results:
        output_path = Path(__file__).parent / args.output
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 结果已保存到: {output_path}")
        print(f"   共 {len(results)} 个产品")
