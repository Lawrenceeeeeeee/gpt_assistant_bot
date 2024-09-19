from alipay import AliPay, DCAliPay, ISVAliPay
from alipay.utils import AliPayConfig

app_private_key_string = open("/root/gpt_assistant_bot/.secret/private_key.pem").read()
alipay_public_key_string = open("/root/gpt_assistant_bot/.secret/alipay_public_key.pem").read()

alipay = AliPay(
    appid="2021004166602194",
    app_notify_url=None,  # 默认回调 url
    app_private_key_string=app_private_key_string,
    # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
    alipay_public_key_string=alipay_public_key_string,
    sign_type="RSA2",  # RSA 或者 RSA2
    debug=True,  # 默认 False
    verbose=True,  # 输出调试数据
    config=AliPayConfig(timeout=15)  # 可选，请求超时时间
)

subject = "测试订单"

# 电脑网站支付，需要跳转到：https://openapi.alipay.com/gateway.do? + order_string
order_string = alipay.api_alipay_trade_page_pay(
    out_trade_no="20240809",
    total_amount=0.01,
    subject=subject,
    return_url="https://www.kookapp.cn/app/channels/3469978858181038/8460960305669548",
)

print(f"https://openapi.alipay.com/gateway.do?{order_string}")
