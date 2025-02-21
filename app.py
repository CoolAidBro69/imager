import streamlit as st
import tweepy
import requests
from requests_oauthlib import OAuth1
from PIL import Image
import tempfile
import os

# ------------------------------------------------------------------
# X (Twitter) App credentials (OAuth 1.0a: Consumer Key & Consumer Secret)
# ------------------------------------------------------------------
CONSUMER_KEY = "Jf72DRWCq4OQaEWxHpmZo8Z29"
CONSUMER_SECRET = "6VhYEVYnSQ1yYGa4pnlXBtyddggiEaydmmq6f90LLyIuvXJI8x"

# ------------------------------------------------------------------
# Authenticate user with PIN-based OAuth
# ------------------------------------------------------------------
def authenticate_user_pin():
    st.subheader("Authenticate with X (PIN-based OAuth)")
    
    if st.button("Start OAuth Flow"):
        auth = tweepy.OAuth1UserHandler(CONSUMER_KEY, CONSUMER_SECRET, callback="oob")
        try:
            redirect_url = auth.get_authorization_url()
            st.session_state["request_token"] = auth.request_token
            st.write("Visit the URL below to authorize the app:")
            st.markdown(f"[Authorize Access]({redirect_url})")
        except tweepy.TweepyException as e:
            st.error(f"Error obtaining request token: {e}")
    
    pin = st.text_input("Enter the PIN provided by X")
    if st.button("Verify PIN"):
        if "request_token" not in st.session_state:
            st.warning("You must start the OAuth flow first.")
        elif not pin:
            st.warning("Please enter the PIN.")
        else:
            auth = tweepy.OAuth1UserHandler(CONSUMER_KEY, CONSUMER_SECRET)
            auth.request_token = st.session_state["request_token"]
            try:
                auth.get_access_token(pin)
                st.session_state["access_token"] = auth.access_token
                st.session_state["access_token_secret"] = auth.access_token_secret
                st.success("Authentication successful!")
            except tweepy.TweepyException as e:
                st.error(f"Error obtaining access token: {e}")

# ------------------------------------------------------------------
# Get Tweepy API object using stored access tokens (for verifying credentials)
# ------------------------------------------------------------------
def get_twitter_api():
    if "access_token" in st.session_state and "access_token_secret" in st.session_state:
        auth = tweepy.OAuth1UserHandler(
            CONSUMER_KEY,
            CONSUMER_SECRET,
            st.session_state["access_token"],
            st.session_state["access_token_secret"]
        )
        return tweepy.API(auth)
    return None

# ------------------------------------------------------------------
# Image uploading and resizing functionality
# ------------------------------------------------------------------
def handle_image_resize():
    st.subheader("Upload and Resize Image")
    uploaded_file = st.file_uploader("Choose an image file:", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", use_container_width=True)
        except Exception as e:
            st.error("Error loading image. Please try a valid image file.")
            st.stop()
        
        # Predefined dimension presets (modifiable via settings)
        default_sizes = {
            "300x250": (300, 250),
            "728x90": (728, 90),
            "160x600": (160, 600),
            "300x600": (300, 600)
        }
        st.write("Configure Desired Dimensions (Optional):")
        custom_sizes = {}
        for label, (w, h) in default_sizes.items():
            col1, col2 = st.columns(2)
            with col1:
                new_w = st.number_input(f"Width for {label}", value=w, step=1, key=f"{label}_w")
            with col2:
                new_h = st.number_input(f"Height for {label}", value=h, step=1, key=f"{label}_h")
            custom_sizes[label] = (new_w, new_h)
        
        st.subheader("Resized Image Previews")
        resized_images = {}
        for label, (width, height) in custom_sizes.items():
            try:
                resized_img = image.resize((width, height))
                resized_images[label] = resized_img
                st.image(resized_img, caption=f"{label}: {width}x{height}", use_container_width=False)
            except Exception as e:
                st.error(f"Error resizing image for {label}: {e}")
        return resized_images, custom_sizes
    return None, None

# ------------------------------------------------------------------
# Upload media using X API v2
# ------------------------------------------------------------------
def upload_media_v2(filename):
    """
    Uploads media using the X API v2 media upload endpoint.
    Returns the media_id on success.
    """
    url = "https://api.x.com/2/media/upload"
    with open(filename, 'rb') as f:
        files = {'media': f}
        auth = OAuth1(
            CONSUMER_KEY,
            CONSUMER_SECRET,
            st.session_state["access_token"],
            st.session_state["access_token_secret"]
        )
        response = requests.post(url, files=files, auth=auth)
    if response.status_code != 200:
        raise Exception(f"Media upload failed: {response.status_code} {response.text}")
    json_response = response.json()
    # Try to get media_id from "data" first, then fallback to "id"
    media_id = None
    if "data" in json_response:
        media_id = json_response.get("data", {}).get("media_id")
    elif "id" in json_response:
        media_id = json_response.get("id")
    if not media_id:
        raise Exception(f"Media upload failed to return a valid media_id: {json_response}")
    return media_id

# ------------------------------------------------------------------
# Publish post with attached media using X API v2
# ------------------------------------------------------------------
def post_tweet_with_media_v2(media_id, text):
    """
    Publishes a post with attached media using the X API v2 posts endpoint.
    Returns the JSON response on success.
    """
    url = "https://api.x.com/2/posts"
    data = {
        "text": text,
        "media": {
            "media_ids": [media_id]
        }
    }
    auth = OAuth1(
        CONSUMER_KEY,
        CONSUMER_SECRET,
        st.session_state["access_token"],
        st.session_state["access_token_secret"]
    )
    response = requests.post(url, json=data, auth=auth)
    if response.status_code != 201:
        raise Exception(f"Post tweet failed: {response.status_code} {response.text}")
    return response.json()

# ------------------------------------------------------------------
# Publish resized images: Upload each media and post a tweet with the media attached.
# ------------------------------------------------------------------
def publish_images():
    # Ensure image is uploaded and resized
    resized_images, custom_sizes = handle_image_resize()
    if resized_images is None:
        st.info("Please upload an image to resize and publish.")
        return

    if st.button("Publish Resized Images to Your Timeline"):
        try:
            for label, img in resized_images.items():
                # Save the resized image to a temporary file
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                    img.save(tmp_file.name)
                    filename = tmp_file.name

                status_text = f"Resized image: {label} ({custom_sizes[label][0]}x{custom_sizes[label][1]})"
                # Upload media using the new v2 endpoint
                media_id = upload_media_v2(filename)
                # Publish post with the attached media
                post_response = post_tweet_with_media_v2(media_id, status_text)
                os.remove(filename)
            st.success("All resized images have been published successfully!")
        except Exception as e:
            st.error(f"Failed to publish images: {e}")

# ------------------------------------------------------------------
# Main Streamlit App
# ------------------------------------------------------------------
def main():
    st.title("X (Twitter) PIN-based OAuth, Image Resizer & Publisher using API v2")
    
    # Step 1: Authentication
    if "access_token" not in st.session_state:
        authenticate_user_pin()
    else:
        st.success("You are authenticated!")
        api = get_twitter_api()
        if api:
            try:
                user = api.verify_credentials()
                st.write(f"Logged in as **@{user.screen_name}**.")
            except Exception as e:
                st.error(f"Error fetching user profile: {e}")
    
    # Step 2: Image Processing & Automatic Publishing
    st.subheader("Image Processing & Publishing")
    publish_images()

if __name__ == "__main__":
    main()
