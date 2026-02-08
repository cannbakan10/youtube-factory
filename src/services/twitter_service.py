import os
import tweepy
from src.utils.logger import get_logger

logger = get_logger(__name__)

class TwitterService:
    def __init__(self):
        self.api_key = os.getenv("X_API_KEY")
        self.api_secret = os.getenv("X_API_SECRET")
        self.access_token = os.getenv("X_ACCESS_TOKEN")
        self.access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")
        self.bearer_token = os.getenv("X_BEARER_TOKEN")

        # V2 Client for posting (Standard)
        self.client = None
        # V1.1 API for Media Uploads (Required for images/videos)
        self.auth = None
        self.api_v1 = None

        self._authenticate()

    def _authenticate(self):
        try:
            # Client for V2 (Tweets)
            self.client = tweepy.Client(
                bearer_token=self.bearer_token,
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret,
                wait_on_rate_limit=True
            )

            # Auth for V1.1 (Media)
            self.auth = tweepy.OAuth1UserHandler(
                self.api_key, self.api_secret, self.access_token, self.access_token_secret
            )
            self.api_v1 = tweepy.API(self.auth)
            
            logger.info("X (Twitter) Service Authenticated successfully.")
        except Exception as e:
            logger.error(f"X Authentication failed: {e}")

    def post_text(self, text: str):
        """Post a simple text tweet."""
        try:
            response = self.client.create_tweet(text=text)
            logger.info(f"Tweet posted successfully! ID: {response.data['id']}")
            return response.data['id']
        except Exception as e:
            logger.error(f"Error posting text tweet: {e}")
            print(f"DEBUG: Text post failed with error: {e}")
            return None

    def post_with_media(self, text: str, media_path: str):
        """Post a tweet with an image or video."""
        try:
            if not os.path.exists(media_path):
                logger.error(f"Media file not found: {media_path}")
                return None

            # Upload media using V1.1
            media = self.api_v1.media_upload(filename=media_path)
            media_id = media.media_id

            # Post tweet with media using V2
            response = self.client.create_tweet(text=text, media_ids=[media_id])
            logger.info(f"Tweet with media posted! ID: {response.data['id']}")
            return response.data['id']
        except Exception as e:
            logger.error(f"Error posting media tweet: {e}")
            print(f"DEBUG: Media post failed with error: {e}")
            return None

    def post_thread(self, tweets: list):
        """Post a thread of tweets."""
        last_tweet_id = None
        try:
            for i, tweet_text in enumerate(tweets):
                if i == 0:
                    response = self.client.create_tweet(text=tweet_text)
                else:
                    response = self.client.create_tweet(
                        text=tweet_text, 
                        in_reply_to_tweet_id=last_tweet_id
                    )
                last_tweet_id = response.data['id']
                logger.info(f"Thread part {i+1} posted.")
            return True
        except Exception as e:
            logger.error(f"Error posting thread: {e}")
            return False
