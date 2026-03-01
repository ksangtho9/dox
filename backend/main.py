import zipfile
import shutil
import tempfile
import json
import re
import uvicorn
import util.methods as methods
import util.consts as consts
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title = "repo analyzer")

@app.post('/analyze')
async def generate_md(zip_file: Path, dest: Path) -> Path:
    return