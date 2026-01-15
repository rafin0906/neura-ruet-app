from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.cr_models import CR

bearer_scheme = HTTPBearer(auto_error=False)


def get_cr_from_setup_token(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if not creds:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    token = creds.credentials

    cr = (
        db.query(CR)
        .filter(CR.setup_token == token)
        .first()
    )

    if not cr:
        raise HTTPException(status_code=401, detail="Invalid or expired setup token")

    return cr
