from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder


def success(data=None, message="Success", status_code=200):
    return JSONResponse(
        status_code=status_code,
        content={
            "message": message,
            "data": jsonable_encoder(data) if data is not None else None
        }
    )
