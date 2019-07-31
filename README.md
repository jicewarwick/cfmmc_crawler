# 批量下载中国期货市场监控中心日结算单
Manual:
1. 在 `config.json` 里填写相关信息. 模板文件为 `config_example.json`
    - 日期格式需为 `%Y%m%d`, 例如 `20190603`.
2. 运行 `cfmmc_crawler.py`.

Misc:
- 登录需提供验证码. 现在的处理方式是弹窗手工输入. 
- 结算单保存于 `output_dir/fund_name/broker_account_no/月报(日报)/ 逐日(逐笔)/account_no_月份(日期).xls`
- 借鉴(~~抄袭~~)了 [cfmmc_spider](https://github.com/sfl666/cfmmc_spider), 感谢 [sfl666](https://github.com/sfl666)

Dependencies:
- bs4
- lxml
- PIL(pillow)

Optional:
- tushare
