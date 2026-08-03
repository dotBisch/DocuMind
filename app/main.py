from fastapi import FastAPI

app = FastAPI(title="DocuMind")


@app.get("/health")
def health():
    return {"status": "ok"}
