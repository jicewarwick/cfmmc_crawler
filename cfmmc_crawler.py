import datetime as dt
import json
import os
import time
from io import BytesIO

import tushare as ts
from PIL import Image
from bs4 import BeautifulSoup
from requests import session


def get_trading_days(config: dict) -> list:
    '''
    # 通过tushare获取期货交易日历
    :param config: 含有 %Y%m%d 格式的 start_date 和 end_date 的字典
    :return: 交易日
    '''
    pro = ts.pro_api(config['tushare_token'])
    df = pro.query('trade_cal', exchange='DCE', start_date=config['start_date'], end_date=config['end_date'], is_open=1)
    date_str = df['cal_date'].values.tolist()
    return [dt.datetime.strptime(it, '%Y%m%d') for it in date_str]


def do_query(config: dict, query_dates: list) -> None:
    '''
    下载每日对账单
    :param config: 包含账户信息和目标输出目录的字典
    :param query_dates: 查询日期
    :return: None
    '''
    base_url = "https://investorservice.cfmmc.com"
    login_url = base_url + '/login.do'
    logout_url = base_url + '/logout.do'
    data_url = base_url + '/customer/setParameter.do'
    excel_download_url = base_url + '/customer/setupViewCustomerDetailFromCompanyWithExcel.do'

    header = {
        'Connection': 'keep-alive',
        'User-Agent': "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.121 Safari/537.36",
    }

    # get CAPTCHA
    ss = session()
    res = ss.get(login_url, headers=header)
    bs = BeautifulSoup(res.text, features="lxml")
    token = bs.body.form.input['value']
    verification_code_url = base_url + bs.body.form.img['src']
    tmp_file = BytesIO()
    tmp_file.write(ss.get(verification_code_url).content)
    img = Image.open(tmp_file)
    img.show()
    verification_code = input('请输入验证码: ')

    # log in
    post_data = {
        "org.apache.struts.taglib.html.TOKEN": token,
        "showSaveCookies": '',
        "userID": config['account_no'],
        "password": config['password'],
        "vericode": verification_code,
    }
    data_page = ss.post(login_url, data=post_data, headers=header, timeout=5)

    if "验证码错误" in data_page.text:
        print('登录失败, 验证码错误!')
    else:
        print('登录成功...')

        # download data day by day
        for date in query_dates:
            tradeDate = date.strftime('%Y-%m-%d')
            file_name = config['account_name'] + ' - ' + tradeDate + '.xls'
            full_path = os.path.join(config['output_dir'], file_name)

            token = BeautifulSoup(data_page.text, features="lxml").form.input['value']
            post_data = {
                "org.apache.struts.taglib.html.TOKEN": token,
                "tradeDate": tradeDate,
                "byType": 'trade'
            }
            data_page = ss.post(data_url, data=post_data, headers=header, timeout=5)

            excel_response = ss.get(excel_download_url)
            with(open(full_path, 'wb')) as f:
                f.write(excel_response.content)
            print('下载', file_name, '完成!')
            time.sleep(1)

        ss.post(logout_url)


if __name__ == '__main__':
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    # integrity check
    needed_keys = ['tushare_token', 'account_name', 'account_no', 'password', 'start_date', 'end_date', 'output_dir']
    for key in needed_keys:
        if key not in config.keys():
            raise ValueError(key + '不在config中')

    query_dates = get_trading_days(config)
    do_query(config, query_dates)
