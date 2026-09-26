from fastapi import FastAPI

app = FastAPI(title="HaramaIn Backend API")


@app.get("/")
def home():
    return {
        "application": "HaramaIn",
        "status": "online"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }