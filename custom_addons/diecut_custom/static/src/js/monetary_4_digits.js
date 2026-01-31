/** @odoo-module **/

import { registry } from "@web/core/registry";
import { MonetaryField } from "@web/views/fields/monetary/monetary_field";
import { formatFloat } from "@web/core/utils/numbers";

export class Monetary4DigitsField extends MonetaryField {
    get formattedValue() {
        const value = this.props.record.data[this.props.name];

        // 如果没有值，返回空
        if (value === null || value === undefined) {
            return "";
        }

        // 强制使用 4 位小数格式化数字
        const formattedNumber = formatFloat(value, { digits: [16, 4] });

        // 获取当前字段相关的货币
        // 尝试使用父类的 currency getter，如果不可用则尝试通过 props 获取
        // 注意：MonetaryField 在不同版本中获取 currency 的方式可能不同
        let currency = null;
        try {
            currency = this.currency;
        } catch (e) {
            // ignore
        }

        // 作为备选，尝试从 props 中获取 (Odoo 17+ 结构)
        if (!currency && this.props.record.data[this.props.currencyField]) {
            // 这是一个简化的获取方式，真正的 MonetaryField 可能需要通过 session 或 currencyId 加载货币符号
            // 如果无法简单获取，我们至少显示数值
        }

        if (currency) {
            if (currency.position === "after") {
                return `${formattedNumber}\u00A0${currency.symbol}`;
            } else {
                return `${currency.symbol}\u00A0${formattedNumber}`;
            }
        }

        return formattedNumber;
    }
}

Monetary4DigitsField.template = "web.MonetaryField";
Monetary4DigitsField.props = {
    ...MonetaryField.props,
};
Monetary4DigitsField.supportedTypes = ["monetary", "float"];

registry.category("fields").add("monetary_4_digits", Monetary4DigitsField);
