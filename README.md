# 批量下载中国期货市场监控中心日结算单
Manual:
1. 在 `config.json` 里填写相关信息. 模板文件为 `config_example.json`
    - 日期格式需为 `%Y%m%d`, 例如 `20190603`.
2. 运行 `cfmmc_crawler.py`.

Misc:
- 登录需提供验证码. 现在的处理方式是弹窗手工输入. 
- `cfmmc_crawler.py` 下载的是逐笔对冲日结算单. 其他类型(逐日盯市)和周期(每月)可通过修改 `post_data` 完成.
- 多账户操作可循环调用 `do_query` 函数.
- 深度借鉴(~~抄袭~~)了 [cfmmc_spider](https://github.com/sfl666/cfmmc_spider), 感谢 [sfl666](https://github.com/sfl666)

Dependencies:
- bs4
- lxml
- PIL
- tushare
