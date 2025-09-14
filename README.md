# AiGen
​Deployable Image Generation Telegram Bot
​This project provides the complete source code for a Telegram bot that generates images from text prompts and is ready for deployment on Render.
​Deployment to Render
​Go to your Render Dashboard.
​Click New + and select Web Service.
​Connect the GitHub repository you just created.
​Render will automatically detect the render.yaml file and fill in most settings.
​Scroll down to Environment Variables and add your two secret keys:
​Key: GEMINI_API_KEY | Value: YOUR_GEMINI_KEY_HERE
​Key: TELEGRAM_TOKEN | Value: YOUR_TELEGRAM_TOKEN_HERE
​Click Create Web Service.
​Render will now build and deploy your bot. Once the logs say it's live, your bot will be running!
