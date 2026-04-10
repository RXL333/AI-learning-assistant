import uvicorn

HOST = "127.0.0.1"
PORT = 8001


if __name__ == "__main__":
    print(f"Backend is running at http://{HOST}:{PORT}")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
