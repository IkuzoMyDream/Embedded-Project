from fastapi import FastAPI
from fastapi.responses import FileResponse

app = FastAPI()

@app.get("/dash")
def dash():
    return FileResponse("client/pages/dash.html")

@app.get("/queue")
def queue():
    return FileResponse("client/pages/queue.html")
