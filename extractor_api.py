import base64
import zipfile
import pymupdf
from fastapi import UploadFile, HTTPException
import io


async def process_file_extraction(file: UploadFile):
    filename = file.filename.lower()
    content = await file.read()

    pages = []

    if filename.endswith(".zip") or filename.endswith(".cbz"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                image_entries = []
                for name in z.namelist():
                    lower_name = name.lower()
                    if (
                        name.endswith("/")
                        or "__MACOSX" in name
                        or name.split("/")[-1].startswith("._")
                    ):
                        continue
                    if lower_name.endswith(
                        (".jpg", ".jpeg", ".png", ".webp", ".avif", ".jxl")
                    ):
                        image_entries.append(name)

                import re

                def natural_sort_key(s):
                    return [
                        int(text) if text.isdigit() else text.lower()
                        for text in re.split("([0-9]+)", s)
                    ]

                image_entries.sort(key=natural_sort_key)

                for index, name in enumerate(image_entries):
                    img_data = z.read(name)
                    base64_data = base64.b64encode(img_data).decode("utf-8")
                    file_ext = name.split(".")[-1].lower()
                    if file_ext == "jpg":
                        file_ext = "jpeg"

                    pages.append(
                        {
                            "filename": name.split("/")[-1],
                            "mime_type": f"image/{file_ext}",
                            "base64": base64_data,
                        }
                    )
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to extract ZIP: {str(e)}"
            )

    elif filename.endswith(".pdf"):
        try:
            doc = pymupdf.open(stream=content, filetype="pdf")
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                zoom = 2.0
                mat = pymupdf.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_data = pix.tobytes("jpeg")
                base64_data = base64.b64encode(img_data).decode("utf-8")
                pad_index = str(page_num + 1).zfill(3)
                original_name = file.filename.rsplit(".", 1)[0]

                pages.append(
                    {
                        "filename": f"{original_name}_page_{pad_index}.jpg",
                        "mime_type": "image/jpeg",
                        "base64": base64_data,
                    }
                )
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to extract PDF: {str(e)}"
            )
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    return {"success": True, "pages": pages}
