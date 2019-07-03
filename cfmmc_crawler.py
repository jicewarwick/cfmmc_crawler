import datetime as dt
import json
import os
from io import BytesIO

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
    query_type_dict = {'逐日盯市': 'day', '逐笔对冲': 'trade'}

    def __init__(self, account_name: str, account_no: str, password: str, output_dir: str, tushare_token: str):
        self.account_name, self.account_no, self.password = account_name, account_no, password

        self.output_dir = output_dir
        self.tushare_token = tushare_token

        self.ss = session()
        self.is_logged_in = False
        self.token = None

    def login(self) -> None:
        """
        登录
        :return: None
        """
        # get CAPTCHA
        res = self.ss.get(self.login_url, headers=self.header)
        bs = BeautifulSoup(res.text, features="lxml")
        token = bs.body.form.input['value']
        verification_code_url = self.base_url + bs.body.form.img['src']
        tmp_file = BytesIO()
        tmp_file.write(self.ss.get(verification_code_url).content)
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
        data_page = self.ss.post(self.login_url, data=post_data, headers=self.header, timeout=5)

        if "验证码错误" in data_page.text:
            print('登录失败, 验证码错误!')
        else:
            print('登录成功...')
            self.is_logged_in = True
            self.token = BeautifulSoup(data_page.text, features="lxml").form.input['value']

    def logout(self) -> None:
        """
        登出
        :return: None
        """
        self.ss.post(self.logout_url)
        self.is_logged_in = False

    def _check_args(self, query_type: str) -> None:
        if not self.is_logged_in:
            raise RuntimeError('需要先登录成功才可进行查询!')

        if query_type not in self.query_type_dict.keys():
            raise ValueError('query_type 必须为 逐日盯市 或 逐笔对冲 !')

    def get_daily_data(self, date: dt.date, query_type: str) -> None:
        """
        下载日报数据到`output_dir/account_name/日报/ 逐日盯市 或 逐笔对冲/月份.xls`
        :param date: 日期
        :param query_type: 逐日盯市 或 逐笔对冲
        :return: None
        """
        self._check_args(query_type)

        trade_date = date.strftime('%Y-%m-%d')
        path = os.path.join(self.output_dir, self.account_name, '日报', query_type)
        file_name = trade_date + '.xls'
        full_path = os.path.join(path, file_name)
        os.makedirs(path, exist_ok=True)

        post_data = {
            "org.apache.struts.taglib.html.TOKEN": self.token,
            "tradeDate": trade_date,
            "byType": query_type
        }
        data_page = self.ss.post(self.data_url, data=post_data, headers=self.header, timeout=5)
        self.token = BeautifulSoup(data_page.text, features="lxml").form.input['value']

        self._download_file(self.excel_daily_download_url, full_path)

    def get_monthly_data(self, month: dt.date, query_type: str) -> None:
        """
        下载月报数据到`output_dir/account_name/月报/ 逐日盯市 或 逐笔对冲/月份.xls`
        :param month: 日期
        :param query_type: 逐日盯市 或 逐笔对冲
        :return: None
        """
        self._check_args(query_type)

        trade_date = month.strftime('%Y-%m')
        path = os.path.join(self.output_dir, self.account_name, '月报', query_type)
        file_name = trade_date + '.xls'
        full_path = os.path.join(path, file_name)
        os.makedirs(path, exist_ok=True)

        post_data = {
            "org.apache.struts.taglib.html.TOKEN": self.token,
            "tradeDate": trade_date,
            "byType": self.query_type_dict[query_type]
        }
        data_page = self.ss.post(self.data_url, data=post_data, headers=self.header, timeout=5)
        self.token = BeautifulSoup(data_page.text, features="lxml").form.input['value']

        self._download_file(self.excel_monthly_download_url, full_path)

    def _download_file(self, web_address: str, full_path: str) -> None:
        excel_response = self.ss.get(web_address)
        with(open(full_path, 'wb')) as fh:
            fh.write(excel_response.content)
        print('下载 ', full_path, ' 完成!')

    def get_trading_days(self, start_date: str, end_date: str) -> list:
        """
        # 通过tushare获取期货交易日历
        :param start_date: 开始时间
        :param end_date: 结束时间
        :return: 期间的时间列表
        """
        import tushare as ts
        pro = ts.pro_api(self.tushare_token)
        df = pro.query('trade_cal', exchange='DCE', start_date=start_date, end_date=end_date, is_open=1)
        date_str = df['cal_date'].values.tolist()
        return [dt.datetime.strptime(it, '%Y%m%d') for it in date_str]

    def batch_daily_download(self, start_date: str, end_date: str) -> None:
        """
        下载查询期间的日报数据到`output_dir/account_name/日报/ 逐日盯市 或 逐笔对冲/日期.xls`
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
        下载查询期间的月报数据到`output_dir/account_name/月报/ 逐日盯市 或 逐笔对冲/月份.xls`
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return: None
        """
        query_months = self._generate_months_first_day(start_date, end_date)
        for month in query_months:
            for query_type in self.query_type_dict.keys():
                self.get_monthly_data(month, query_type)

    @staticmethod
    def _generate_months_first_day(start_date: str, end_date: str) -> list:
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
    needed_keys = ['tushare_token', 'account_name', 'account_no', 'password', 'start_date', 'end_date', 'output_dir']
    for key in needed_keys:
        if key not in config.keys():
            raise ValueError(key + '不在config中')

    # let it begin
    crawler = CFMMCCrawler(config['account_name'], config['account_no'], config['password'],
                           config['output_dir'], config['tushare_token'])
    crawler.login()
    crawler.batch_daily_download(config['start_date'], config['end_date'])
    crawler.batch_monthly_download(config['start_date'], config['end_date'])
