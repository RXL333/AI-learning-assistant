def ok(data=None, message: str = "success"):
    return {"code": 0, "message": message, "data": data if data is not None else {}}


def err(code: int, message: str):
    return {"code": code, "message": message, "data": {}}
