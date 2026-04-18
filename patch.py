import sys
import os

filename = r'e:\workspace\my_odoo_project\custom_addons\diecut\static\src\js\material_split_preview.js'
with open(filename, 'r', encoding='utf-8') as f:
    content = f.read()

target1 = '''        this.state = useState({
            viewportWidth: window.innerWidth,
            resizing: false,
            selectedResId: null,
            refreshTick: 0,'''

replacement1 = '''        this.state = useState({
            viewportWidth: window.innerWidth,
            resizing: false,
            selectedResId: null,
            formResId: null,
            refreshTick: 0,'''

target2 = '''        this._liveSplitRatio = this.props.splitRatio || 45;
        this._rafResizeTick = null;
        this._lastPointerEvent = null;'''

replacement2 = '''        this._liveSplitRatio = this.props.splitRatio || 45;
        this._rafResizeTick = null;
        this._lastPointerEvent = null;
        this._formLoadTimeout = null;'''

target3 = '''        onWillUnmount(() => {
            window.removeEventListener("resize", this._onWindowResize);
            window.removeEventListener("mousemove", this._onPointerMove);
            window.removeEventListener("mouseup", this._onPointerUp);
            if (this._rafResizeTick) {
                window.cancelAnimationFrame(this._rafResizeTick);
                this._rafResizeTick = null;
            }
        });'''

replacement3 = '''        onWillUnmount(() => {
            window.removeEventListener("resize", this._onWindowResize);
            window.removeEventListener("mousemove", this._onPointerMove);
            window.removeEventListener("mouseup", this._onPointerUp);
            if (this._rafResizeTick) {
                window.cancelAnimationFrame(this._rafResizeTick);
                this._rafResizeTick = null;
            }
            if (this._formLoadTimeout) {
                clearTimeout(this._formLoadTimeout);
            }
        });'''

def fix_crlf(s):
    return s.replace('\\n', '\\r\\n')

# try with both CRLF and LF
if fix_crlf(target1) in content:
    content = content.replace(fix_crlf(target1), fix_crlf(replacement1))
elif target1 in content:
    content = content.replace(target1, replacement1)

if fix_crlf(target2) in content:
    content = content.replace(fix_crlf(target2), fix_crlf(replacement2))
elif target2 in content:
    content = content.replace(target2, replacement2)

if fix_crlf(target3) in content:
    content = content.replace(fix_crlf(target3), fix_crlf(replacement3))
elif target3 in content:
    content = content.replace(target3, replacement3)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done.')
