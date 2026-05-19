from loguru import logger
from app import create_app

logger.add("logs/app.log", rotation="10 MB", retention="7 days", level="INFO")

app = create_app()

if __name__ == "__main__":
    logger.info("Starting WebAnalyzer server on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", debug=False, port=5000)
