import datetime
import time

from s3p_sdk.plugin.payloads.parsers import S3PParserBase
from s3p_sdk.exceptions.parser import S3PPluginParserOutOfRestrictionException, S3PPluginParserFinish
from s3p_sdk.types import S3PRefer, S3PDocument, S3PPlugin, S3PPluginRestrictions
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from s3p_sdk.types.plugin_restrictions import FROM_DATE
import dateutil.parser
from bs4 import BeautifulSoup


class ECB(S3PParserBase):
    """
    A Parser payload that uses S3P Parser base class.
    """

    HOST = 'https://www.ecb.europa.eu/pub/pubbydate/html/index.en.html'
    YEARS = [2025, 2024]
    DOMAIN = 'https://www.ecb.europa.eu'

    def __init__(self, refer: S3PRefer, plugin: S3PPlugin, restrictions: S3PPluginRestrictions, web_driver: WebDriver):
        super().__init__(refer, plugin, restrictions)

        # Тут должны быть инициализированы свойства, характерные для этого парсера. Например: WebDriver
        self._driver = web_driver
        self._wait = WebDriverWait(self._driver, timeout=20)

    def _parse(self) -> None:

        self._driver.get(self.HOST)
        time.sleep(5)

        try:
            self._driver.find_elements(By.XPATH, "//a[contains(text(),'I understand and I accept')]")[0].click()
            time.sleep(0.5)
        except:
            pass

        lazy_load = self._driver.find_element(By.CLASS_NAME, 'lazy-load-hit')


        # Теперь на сайте один контейнер со всеми публикациями
        dl_wrapper = self._driver.find_element(By.CLASS_NAME, 'dl-wrapper')

        height_dl_wrapper = 0

        while True:
            # Прокрутка страницы до конца
            try:

                self._driver.execute_script("arguments[0].scrollIntoView();", lazy_load)
                time.sleep(0.1)
                # Проверка. Если появятся новые записи, то высота контента изменится
                # ! Можно оценивать количество элементов.
                if dl_wrapper.size['height'] > height_dl_wrapper:
                    height_dl_wrapper = dl_wrapper.size['height']
                    time.sleep(1)
                else:
                    break
            except Exception as e:
                break

        soup = BeautifulSoup(self._driver.page_source, 'html.parser')
        els = soup.find('div', class_='sort-wrapper').find('dl').find_all('dd')

        web_links = []

        for el in els:
            try:
                web_links.append(el.find('div').find('div', class_='title').find('a')['href'])
            except:
                pass

        for web_link in web_links:

            if web_link.endswith('html'):
                try:

                    url = self.DOMAIN+web_link
                    self._driver.get(url)
                    self.logger.debug('Entered on web page ' + url)
                    time.sleep(2)

                    article = self._driver.find_element(By.TAG_NAME, 'main')
                    title = article.find_element(By.XPATH, ".//div[@class='title']//h1").text
                    try:
                        category = article.find_element(By.XPATH, ".//div[@class='title']//ul/li").text
                    except:
                        category = None
                    pub_date = dateutil.parser.parse(
                        article.find_element(By.CLASS_NAME, 'ecb-publicationDate').text)
                    text = article.find_element(By.CLASS_NAME, 'section').text
                    try:
                        abstract = article.find_element(By.CLASS_NAME, 'section').find_elements(By.TAG_NAME, 'ul')[
                        0].text
                    except:
                        abstract=None
                    try:
                        text += '\n\n' + self._driver.find_element(By.CLASS_NAME, 'footnotes').text
                    except:
                        pass

                    doc = S3PDocument(
                        id=None,
                        title=title,
                        abstract=abstract,
                        text=text,
                        link=web_link,
                        storage=None,
                        other={'category': category},
                        published=pub_date,
                        loaded=None,
                    )
                except Exception as e:
                    self.logger.error(e)
                    continue
                else:
                    try:
                        self._find(doc)
                    except S3PPluginParserOutOfRestrictionException as e:
                        if e.restriction == FROM_DATE:
                            self.logger.debug(f'Document is out of date range `{self._restriction.from_date}`')
                            raise S3PPluginParserFinish(self._plugin,
                                                        f'Document is out of date range `{self._restriction.from_date}`',
                                                        e)

        else:
            self.logger.debug('Section parse error')

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
