import datetime
import time

from s3p_sdk.plugin.payloads.parsers import S3PParserBase
from s3p_sdk.types import S3PRefer, S3PDocument, S3PPlugin, S3PPluginRestrictions
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
import dateutil.parser


class ECB(S3PParserBase):
    """
    A Parser payload that uses S3P Parser base class.
    """

    HOST = 'https://www.ecb.europa.eu/pub/pubbydate/html/index.en.html'
    YEARS = [2025, 2024, 2023, 2022, 2021, 2020]

    def __init__(self, refer: S3PRefer, plugin: S3PPlugin, restrictions: S3PPluginRestrictions, web_driver: WebDriver):
        super().__init__(refer, plugin, restrictions)

        # Тут должны быть инициализированы свойства, характерные для этого парсера. Например: WebDriver
        self._driver = web_driver
        self._wait = WebDriverWait(self._driver, timeout=20)

    def _parse(self) -> None:

        self._driver.get(self.HOST)
        time.sleep(1)

        for year in self.YEARS:

            lazy_load = self._driver.find_element(By.CLASS_NAME, 'lazy-load-hit')

            if year:
                self._select_year('//*[@id="year"]', str(year))
                time.sleep(3)

            # Теперь на сайте один контейнер со всеми публикациями
            dl_wrapper = self._driver.find_element(By.CLASS_NAME, 'dl-wrapper')
            sections = dl_wrapper.find_elements(By.XPATH, '//*[@id="main-wrapper"]/main/div[2]/div[3]/div[2]/div[2]/dl')

            height_dl_wrapper = 0
            for section in sections:
                while True:
                    # Прокрутка страницы до конца
                    self._driver.execute_script("arguments[0].scrollIntoView();", lazy_load)

                    # Проверка. Если появятся новые записи, то высота контента изменится
                    # ! Можно оценивать количество элементов.
                    if dl_wrapper.size['height'] > height_dl_wrapper:
                        height_dl_wrapper = dl_wrapper.size['height']
                        time.sleep(1)
                    else:
                        break

                dts = section.find_elements(By.TAG_NAME, "dt")
                dds = section.find_elements(By.TAG_NAME, "dd")
                if len(dts) == len(dds):
                    for date, body in zip(dts, dds):
                        try:
                            # self.driver.execute_script("arguments[0].scrollIntoView();", body)
                            doc = S3PDocument(
                                None,
                                body.find_element(By.CLASS_NAME, 'title').text,
                                None,
                                None,
                                body.find_element(By.CLASS_NAME, 'title').find_element(By.TAG_NAME,
                                                                                       'a').get_attribute('href'),
                                None,
                                None,
                                dateutil.parser.parse(date.text),
                                None,
                            )
                            try:
                                doc.other = {
                                    'category': body.find_element(By.CLASS_NAME, 'category').text,
                                }
                            except:
                                pass
                            if doc.link.endswith('html'):
                                try:
                                    self._driver.get(doc.link)
                                    self.logger.debug('Entered on web page ' + doc.link)
                                    time.sleep(2)

                                    text = self._driver.find_element(By.CLASS_NAME, 'section').text
                                    print(text)
                                    try:
                                        text += '\n\n' + self._driver.find_element(By.CLASS_NAME, 'footnotes').text
                                    except:
                                        pass
                                    doc.text = text
                                    doc.loaded = datetime.datetime.now()
                                except Exception as e:
                                    self.logger.error(e)
                                else:
                                    self._find(doc)

                        except Exception as e:
                            self.logger.error(e)
                            continue
                else:
                    self.logger.debug('Section parse error')
                break

    def _select_year(self, xpath, value):
        """
        Выбирает один пункт из раскрывающегося списка по его xpath
        """
        try:
            select = self._driver.find_element(By.XPATH, xpath)
            options = select.find_elements(By.TAG_NAME, 'option')
            self.logger.debug(F"Filter by class name: {xpath}")
            for option in options:
                if option.get_attribute('value') == value and WebDriverWait(self._driver, 5).until(
                        ec.element_to_be_clickable(option)):
                    # select.click()
                    option.click()
                    self.logger.debug(F"Choice option '{value}' at select by class name: {xpath}")
                    break
            raise f'The selected value {value} is not found'
        except Exception as e:
            self.logger.debug(f'_select_year func: {e}')
