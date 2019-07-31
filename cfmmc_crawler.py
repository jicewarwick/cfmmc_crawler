import datetime as dt
import json
import os
from io import BytesIO
from typing import Sequence

from PIL import Image
from bs4 import BeautifulSoup
from requests import session


class CFMMCCrawler(object):
    # modular constants, mostly web addresses
    base_url = "https://investorservice.cfmmc.com"
    login_url = base_url + '/login.do'
    logout_url = base_url + '/logout.do'
    data_url = base_url + '/customer/setParameter.do'
    excel_daily_download_url = base_url + '/customer/setupViewCustomerDetailFromCompanyWithExcel.do'
    excel_monthly_download_url = base_url + '/customer/setupViewCustomerMonthDetailFromCompanyWithExcel.do'
    header = {
        'Connection': 'keep-alive',
        'User-Agent': "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.121 Safari/537.36",
    }
    query_type_dict = {'逐日': 'day', '逐笔': 'trade'}

    def __init__(self, fund_name: str, broker: str,
                 account_no: str, password: str,
                 output_dir: str, tushare_token: str) -> None:
        """
        从期货保证金结算中心下载期货结算单到本地
        本地输出地址为 output_dir/fund_name/broker_account_no/日报 或 月报/逐日 或 逐笔/account_no_date.xls
        :param fund_name: 基金名称
        :param broker: 期货公司
        :param account_no: 账号
        :param password: 密码
        :param output_dir: 输出目录
        :param tushare_token: Tushare Token
        """

        self.fund_name, self.broker = fund_name, broker
        self.account_no, self.password = account_no, password

        self.output_dir = output_dir
        self.tushare_token = tushare_token

        self._ss = None
        self.token = None

    def login(self) -> None:
        """
        登录
        """
        # get CAPTCHA
        self._ss = session()
        res = self._ss.get(self.login_url, headers=self.header)
        bs = BeautifulSoup(res.text, features="lxml")
        token = bs.body.form.input['value']
        verification_code_url = self.base_url + bs.body.form.img['src']
        tmp_file = BytesIO()
        tmp_file.write(self._ss.get(verification_code_url).content)
        img = Image.open(tmp_file)
        img.show()
        verification_code = input('请输入验证码: ')

        post_data = {
            "org.apache.struts.taglib.html.TOKEN": token,
            "showSaveCookies": '',
            "userID": self.account_no,
            "password": self.password,
            "vericode": verification_code,
        }
        data_page = self._ss.post(self.login_url, data=post_data, headers=self.header, timeout=5)

        if "验证码错误" in data_page.text:
            print('登录失败, 验证码错误, 请重试!')
        else:
            print('登录成功...')
            self.token = self._get_token(data_page.text)

    def logout(self) -> None:
        """
        登出
        """
        if self.token:
            self._ss.post(self.logout_url)
            self.token = None

    def _check_args(self, query_type: str) -> None:
        if not self.token:
            raise RuntimeError('需要先登录成功才可进行查询!')

        if query_type not in self.query_type_dict.keys():
            raise ValueError('query_type 必须为 逐日 或 逐笔 !')

    def get_daily_data(self, date: dt.date, query_type: str) -> None:
        """
        下载日报数据

        :param date: 日期
        :param query_type: 逐日 或 逐笔
        :return: None
        """
        self._check_args(query_type)

        trade_date = date.strftime('%Y-%m-%d')
        path = os.path.join(self.output_dir, self.fund_name, self.broker + '_' + self.account_no, '日报', query_type)
        file_name = self.account_no + '_' + trade_date + '.xls'
        full_path = os.path.join(path, file_name)
        os.makedirs(path, exist_ok=True)

        post_data = {
            "org.apache.struts.taglib.html.TOKEN": self.token,
            "tradeDate": trade_date,
            "byType": self.query_type_dict[query_type]
        }
        data_page = self._ss.post(self.data_url, data=post_data, headers=self.header, timeout=5)
        self.token = self._get_token(data_page.text)

        self._download_file(self.excel_daily_download_url, full_path)

    def get_monthly_data(self, month: dt.date, query_type: str) -> None:
        """
        下载月报数据

        :param month: 日期
        :param query_type: 逐日 或 逐笔
        :return: None
        """
        self._check_args(query_type)

        trade_date = month.strftime('%Y-%m')
        path = os.path.join(self.output_dir, self.fund_name, self.broker + '_' + self.account_no, '月报', query_type)
        file_name = self.account_no + '_' + trade_date + '.xls'
        full_path = os.path.join(path, file_name)
        os.makedirs(path, exist_ok=True)

        post_data = {
            "org.apache.struts.taglib.html.TOKEN": self.token,
            "tradeDate": trade_date,
            "byType": self.query_type_dict[query_type]
        }
        data_page = self._ss.post(self.data_url, data=post_data, headers=self.header, timeout=5)
        self.token = self._get_token(data_page.text)

        self._download_file(self.excel_monthly_download_url, full_path)

    @staticmethod
    def _get_token(page: str) -> str:
        token = BeautifulSoup(page, features="lxml").form.input['value']
        return token

    def _download_file(self, web_address: str, download_path: str) -> None:
        excel_response = self._ss.get(web_address)
        with(open(download_path, 'wb')) as fh:
            fh.write(excel_response.content)
        print('下载 ', download_path, ' 完成!')

    def get_trading_days(self, start_date: str, end_date: str) -> Sequence[dt.datetime]:
        """
        通过tushare获取区间的交易日

        :param start_date: 开始时间
        :param end_date: 结束时间
        :return: 期间的交易日列表
        """
        import tushare as ts
        pro = ts.pro_api(self.tushare_token)
        df = pro.query('trade_cal', exchange='DCE', start_date=start_date, end_date=end_date, is_open=1)
        date_str = df['cal_date'].values.tolist()
        return [dt.datetime.strptime(it, '%Y%m%d') for it in date_str]

    def batch_daily_download(self, start_date: str, end_date: str) -> None:
        """
        批量日报下载, 包括昨日和逐笔
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return: None
        """
        all_trading_dates = self.get_trading_days(start_date, end_date)
        for date in all_trading_dates:
            for query_type in self.query_type_dict.keys():
                self.get_daily_data(date, query_type)

    def batch_monthly_download(self, start_date: str, end_date: str) -> None:
        """
        批量月报下载, 包括昨日和逐笔
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return: None
        """
        query_months = self._generate_months_first_day(start_date, end_date)
        for month in query_months:
            for query_type in self.query_type_dict.keys():
                self.get_monthly_data(month, query_type)

    @staticmethod
    def _generate_months_first_day(start_date: str, end_date: str) -> Sequence[dt.date]:
        start = dt.date(int(start_date[:4]), int(start_date[4:6]), 1)
        end = dt.date(int(end_date[:4]), int(end_date[4:6]), 1)
        storage = []
        while start <= end:
            storage.append(start)
            start = dt.date(start.year + start.month // 12, (start.month + 1) % 13 + start.month // 12, 1)
        return storage


if __name__ == '__main__':
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    # integrity check
    needed_keys = ['tushare_token', 'accounts', 'start_date', 'end_date', 'output_dir']
    for key in needed_keys:
        if key not in config.keys():
            raise ValueError(key + '不在config中')

    # let it begin
    for account in config['accounts']:
        crawler = CFMMCCrawler(account['fund_name'], account['broker'], account['account_no'], account['password'],
                               config['output_dir'], config['tushare_token'])
        try:
            print('正在登陆 ', account['fund_name'], ' - ', account['broker'])
            while crawler.token is None:
                crawler.login()
        except KeyboardInterrupt:
            continue
        crawler.batch_daily_download(config['start_date'], config['end_date'])
        crawler.batch_monthly_download(config['start_date'], config['end_date'])
        print('完成操作, 登出!')
        crawler.logout()
