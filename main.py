import datetime
import os
import time
import re
from asyncio import run


import pygsheets
import requests
import schedule
import telegram

from publish_on_vk import publish_to_vk, delete_vk_post
from publish_on_ok import publish_to_ok, delete_ok_post

from dotenv import load_dotenv


from spreadsheets import (get_rows_for_posts, get_file, get_parsed_file, update_post_id, get_time_to_post, get_datetime,
                          SMM_TG, SMM_OK, SMM_VK, SMM_DATE_POST, SMM_TIME_POST, SMM_DATE_ACTUAL_POST, SMM_GOOGLE_DOC,
                          SMM_IMAGE_LINK, SMM_TG_POST_ID, SMM_VK_POST_ID, SMM_OK_POST_ID, SMM_DELETE_POST)
from publish_on_tg import send_post, send_animation_image


def fetch_gif_image(image_url):
    url = image_url
    filename = os.path.basename(image_url)
    response = requests.get(url)
    response.raise_for_status()
    with open(filename, 'wb') as file:
        file.write(response.content)
    return filename


def format_text(text):
    formated_txt = re.sub(' +', ' ', text)
    formated_txt = formated_txt.replace(' "', ' «')
    formated_txt = formated_txt.replace('" ', '» ')
    formated_txt = formated_txt.replace(' - ', ' – ')
    return formated_txt



def main():
    load_dotenv()
    # Telegram Secret
    telegram_token = os.getenv('TELEGRAM_TOKEN')
    telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    bot = telegram.Bot(token=telegram_token)
    # vkontakte secret
    vk_token = os.getenv('VK_ACCESS_TOKEN')
    vk_group_id = os.getenv('VK_GROUP_ID')
    vk_ver = '5.131'
    # odnoklasniki secret
    ok_app_key = os.getenv('OK_APPLICATION_KEY')
    ok_access_token = os.getenv('OK_LONG_ACCESS_TOKEN')
    ok_sesion_key = os.getenv('OK_SECRET_SESSION_KEY')
    ok_group_id = os.getenv('OK_GROUP_ID')
    # spreadsheet secret
    service_file_spreadsheet = os.getenv('SERVICE_FILE_SPREADSHEET')
    spreadsheet_smm_key = os.getenv('SPREADSHEET_SMM_KEY')

    gc = pygsheets.authorize(service_file=service_file_spreadsheet)
    spreadsheet_smm = gc.open_by_key(spreadsheet_smm_key)
    worksheet_smm = spreadsheet_smm.sheet1
    min_row = worksheet_smm.cell('M2').value
    max_row = worksheet_smm.rows
    date_now = datetime.datetime.now()
    today = date_now.date().strftime('%d.%m.%Y')
    hour = date_now.strftime('%H:%M:00')
    post_punlish = worksheet_smm.cell(f'M{min_row}').value
    min_range_row = worksheet_smm.cell('M1')
    if post_punlish == 'TRUE' and not worksheet_smm.cell(f'F{min_row}').value:
        min_range_row.value = int(min_row) + 1
    elif post_punlish == 'TRUE' and worksheet_smm.cell(f'F{min_row}').value < today:
        min_range_row.value = int(min_row) + 1
    all_table_rows = worksheet_smm.range(f'{min_row}:{max_row}', returnas='cell')
    rows_for_post, rows_for_delete = get_rows_for_posts(all_table_rows)

    for row in rows_for_post:
        if not row[SMM_DATE_POST].value:
            date_post = today
        else:
            date_post = row[SMM_DATE_POST].value
        if not row[SMM_TIME_POST].value:
            time_post = hour
        else:
            time_post = row[SMM_TIME_POST].value
        datetime_post = get_datetime(date_post, time_post)
        if datetime_post > date_now:
            continue
        file_link = ''
        image_link = ''
        if row[SMM_GOOGLE_DOC].value:
            file_link = row[SMM_GOOGLE_DOC].value
        else:
            image_link = row[SMM_IMAGE_LINK].value
        if file_link:
            downloaded_doc = get_file(file_link)
            text, image = get_parsed_file(downloaded_doc)
            text = format_text(text)
            if row[SMM_TG].value == 'TRUE' and not row[SMM_TG_POST_ID].value:
                post_id = run(send_post(telegram_chat_id, bot, text, image))
                update_post_id(row, post_id, network='TG')
            if row[SMM_VK].value == 'TRUE' and not row[SMM_VK_POST_ID].value:
                post_id = publish_to_vk(image, text, vk_token,
                        vk_group_id, vk_ver)
                update_post_id(row, post_id, network='VK')
            if row[SMM_OK].value == 'TRUE' and not row[SMM_OK_POST_ID].value:
                post_id = publish_to_ok(ok_app_key, ok_access_token, ok_sesion_key, ok_group_id, text, image)
                update_post_id(row, post_id, network='OK')
        elif image_link:
            text = None
            image = fetch_gif_image(image_link)
            bot = telegram.Bot(token=telegram_token)
            if row[SMM_TG].value == 'TRUE' and not row[SMM_TG_POST_ID].value:
                post_id = run(send_animation_image(telegram_chat_id, bot, image))
                update_post_id(row, post_id, network='TG')
            if row[SMM_VK].value == 'TRUE' and not row[SMM_VK_POST_ID].value:
                post_id = publish_to_vk(image, '', vk_token, vk_group_id, vk_ver)
                update_post_id(row, post_id, network='VK')
            if row[SMM_OK].value == 'TRUE' and not row[SMM_OK_POST_ID].value:
                post_id = publish_to_ok(ok_app_key, ok_access_token, ok_sesion_key, ok_group_id, text, image)
                update_post_id(row, post_id, network='OK')
    for row in rows_for_delete:
        delete_date = row[SMM_DATE_ACTUAL_POST].value
        if delete_date > today:
            continue
        if row[SMM_VK_POST_ID].value:
            post_id = row[SMM_VK_POST_ID].value
            delete_vk_post(vk_token, vk_group_id, post_id, vk_ver)
        if row[SMM_TG_POST_ID].value:
            pass
        if row[SMM_OK_POST_ID].value:
            post_id = row[SMM_OK_POST_ID].value
            delete_ok_post(ok_app_key, ok_access_token, ok_sesion_key, post_id)
        row[SMM_DELETE_POST].value = True


if __name__ == '__main__':
    n = os.getenv('TIME_INTERVAL')
    schedule.every(10).seconds.do(main)
    while True:
        print(schedule.next_run())
        schedule.run_pending()
        time.sleep(10)
