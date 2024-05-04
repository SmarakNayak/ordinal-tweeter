import tweepy
import requests
import time
from selenium import webdriver
import chromedriver_autoinstaller
from PIL import Image
from io import BytesIO
import yaml
import os

config_path = os.getenv("TWITTER_CONFIG_PATH")
if config_path is None:
    config_path = "twitter.yaml"

config = yaml.safe_load(open(config_path))
bearer_token = config["bearer_token"]
consumer_key = config["consumer_key"]
consumer_secret = config["consumer_secret"]
access_token = config["access_token"]
access_token_secret = config["access_token_secret"]


def format_size(size_in_bytes):
    if size_in_bytes < 1000:
        return f"{size_in_bytes} bytes"
    elif size_in_bytes < 1000 * 1000:
        return f"{size_in_bytes / 1000:.2f} KB"
    elif size_in_bytes < 1000 * 1000 * 1000:
        return f"{size_in_bytes / (1000 * 1000):.2f} MB"
    else:
        return f"{size_in_bytes / (1000 * 1000 * 1000):.2f} GB"


def get_block_height():
    url = "https://vermilion.place/blockheight"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
        block_height = response.text.strip()
        print(f"Current block height: {block_height}")
        return block_height
    except requests.exceptions.RequestException as e:
        print(f"Error occurred while fetching block height: {e}")


def get_block_icon(block_height):
    url = "https://vermilion.place/api/block_icon/" + block_height

    response = requests.get(url)
    response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes

    # Check if the response contains an image
    content_type = response.headers["Content-Type"]
    if response.headers["Content-Type"].startswith("image/"):
        # Strip the "image/" prefix from the content type
        image_format = content_type.split("/")[1]
        file_extension = f".{image_format}"

        # Save the image to a temporary file
        temp_image_path = f"temp_image{file_extension}"
        with open(temp_image_path, "wb") as file:
            file.write(response.content)
        return temp_image_path
    else:
        raise ValueError("The response does not contain an image.")


def get_image(number):
    url = "https://vermilion.place/api/inscription_number/" + str(number)
    retries = 0
    while retries < 3:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
        if response.text == "This content hasn't been indexed yet.":
            if retries < 2:
                print(f"Content not indexed yet. Retrying in 60 seconds...")
                time.sleep(60)
                retries += 1
                continue
            else:
                raise ValueError("Max retries exceeded. Content not indexed.")

        # Check if the response contains an image
        content_type = response.headers["Content-Type"]
        if response.headers["Content-Type"].startswith("image/"):
            # Strip the "image/" prefix from the content type
            image_format = content_type.split("/")[1]
            file_extension = f".{image_format}"

            # Save the image to a temporary file
            temp_image_path = f"temp_image{file_extension}"
            with open(temp_image_path, "wb") as file:
                file.write(response.content)
            return temp_image_path
        else:
            raise ValueError("The response does not contain an image.")


def get_html(number):
    url = "https://vermilion.place/api/inscription_number/" + str(number)
    retries = 0
    while retries < 3:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
        if response.text == "This content hasn't been indexed yet.":
            if retries < 2:
                print(f"Content not indexed yet. Retrying in 60 seconds...")
                time.sleep(60)
                retries += 1
                continue
            else:
                raise ValueError("Max retries exceeded. Content not indexed.")
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(10)
            driver.get(url)
            driver.set_window_size(1080, 1080)
            time.sleep(10)
            screenshot = driver.get_screenshot_as_png()
            image = Image.open(BytesIO(screenshot))
            image.save('screenshot.png')
            driver.quit()
            return 'screenshot.png'
        except Exception as e:
            raise ValueError(f"Error occurred while fetching html inscription: {e}")


def get_content_path(block_height):
    url = "https://vermilion.place/api/inscriptions_in_block/" + block_height + "?content_types=image,html,gif&sort_by=biggest&page_size=1"
    response = requests.get(url)
    json = response.json()
    if len(json) > 0:
        content_type = json[0]["content_type"]
        content_length = json[0]["content_length"]
        number = json[0]["number"]
        if content_length < 50000:
            raise ValueError(f"Content <50KB")

        if content_type.startswith("text/html") or content_type.startswith("image/svg+xml"):
            path = get_html(number)
            return path, number, content_length
        elif content_type.startswith("image"):
            path = get_image(number)
            return path, number, content_length
        else:
            raise ValueError(f"Unhandled Content Type: {content_type}")
    else:
        raise ValueError(f"No inscriptions in this block")

def send_tweet(client, api, text, image_path):
    print(image_path)
    try:
        media = api.media_upload(image_path)
        client.create_tweet(text=text, media_ids=[media.media_id])
    except tweepy.TweepyException as e:
        print(f"Error sending tweet: {e}")

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # chromedriver_autoinstaller.install()
    client = tweepy.Client(
        consumer_key=consumer_key, consumer_secret=consumer_secret,
        access_token=access_token, access_token_secret=access_token_secret
    )
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)

    bh = "841785"#get_block_height()
    bh_int = int(bh)
    image_path, inscription_number, content_length = get_content_path(bh)
    formatted_blockheight = "{:,}".format(bh_int)
    formatted_number = "{:,}".format(int(inscription_number))
    formatted_size = format_size(content_length)
    send_tweet(client, api,
               'Block ' + formatted_blockheight + '\nInscription ' + formatted_number + '\nSize ' + formatted_size + '\n\nSee more inscriptions from this block at https://vermilion.place/block/' + bh,
               image_path)
    time.sleep(60)
    while True:
        new_bh = get_block_height()
        new_bh_int = int(new_bh)
        if new_bh_int > bh_int:
            bh = new_bh
            bh_int = new_bh_int
            try:
                image_path, inscription_number, content_length = get_content_path(bh)
                formatted_blockheight = "{:,}".format(bh_int)
                formatted_number = "{:,}".format(int(inscription_number))
                formatted_size = format_size(content_length)
                send_tweet(client, api,
                           'Block ' + formatted_blockheight + '\nInscription ' + formatted_number + '\nSize ' + formatted_size + '\n\nSee more inscriptions from this block at https://vermilion.place/block/' + bh,
                           image_path)
                time.sleep(60)
            except Exception as e:
                print(f"Unknown error: {e}")
                time.sleep(60)
        else:
            print(f"New block not detected, latest block: {bh}")
            time.sleep(60)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
