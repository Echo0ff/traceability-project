import json
import logging
import os
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import emails  # type: ignore
import qrcode
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from fastapi import UploadFile
from jinja2 import Template
from jose import JWTError, jwt
from pydantic import TypeAdapter

from app.core.config import settings
from app.core.redis_conf import redis_client

client = AcsClient(settings.ACCESS_KEY_ID, settings.ACCESS_KEY_SECRET,
                   settings.REGION)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def generate_verification_code() -> str:
    verify_str = "".join([str(random.randint(0, 9)) for _ in range(6)])
    logger.info(f"Generating verification code is {verify_str}")
    # return verify_str
    return "9999"


def send_verification_code(phone_number: str, code: str) -> Optional[str]:
    request = CommonRequest()
    request.set_accept_format("json")
    request.set_domain("dysmsapi.aliyuncs.com")
    request.set_method("POST")
    request.set_protocol_type("https")  # https | http
    request.set_version("2017-05-25")
    request.set_action_name("SendSms")

    request.add_query_param("RegionId", settings.REGION)
    request.add_query_param("PhoneNumbers", phone_number)
    request.add_query_param("SignName", "农产品溯源小程序")  # 替换为您的短信签名
    request.add_query_param("TemplateCode", "SMS_468635374")  # 替换为您的短信模板CODE
    request.add_query_param("TemplateParam", json.dumps({"code": code}))

    try:
        response = client.do_action_with_exception(request)
        response_dict = json.loads(response)
        logger.info(f"SMS response: {response_dict}")
        if response_dict.get("Code") == "OK":
            return None  # 表示发送成功
        else:
            return response_dict.get("Message")  # 返回错误信息
    except Exception as e:
        logger.error(f"Error sending SMS: {str(e)}")
        return str(e)


def store_verification_code(phone_number: str,
                            code: str,
                            expire_time: int = 300):
    redis_client.setex(f"verification:{phone_number}", expire_time, code)


def verify_code(phone_number: str, code: str) -> bool:
    stored_code = redis_client.get(f"verification:{phone_number}")
    if stored_code and stored_code == code:
        redis_client.delete(f"verification:{phone_number}")
        return True
    return False


def model_to_dict(obj, output_model):
    return TypeAdapter(output_model).validate_python(obj)


def generate_qr_code(data, prefix="qrcode", directory="qrcodes"):
    """
    Generate a QR code and save it as an image file.

    :param data: The data to be encoded in the QR code.
    :param prefix: Prefix for the filename (default: "qrcode").
    :param directory: Directory to save the QR code image (default: "qrcodes").
    :return: The filename of the generated QR code image.
    """
    # Ensure the directory exists
    os.makedirs(directory, exist_ok=True)

    # Generate a unique filename
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{prefix}_{timestamp}.png"
    filepath = os.path.join(directory, filename)

    # Create QR code instance
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )

    # Add data
    qr.add_data(str(data))
    qr.make(fit=True)

    # Create an image from the QR Code instance
    img = qr.make_image(fill_color="black", back_color="white")

    # Save the image
    img.save(filepath)

    return filename


# def generate_qr_code(id: int, data: str, directory: str) -> str:
#     qr = qrcode.QRCode(
#         version=1,
#         error_correction=qrcode.constants.ERROR_CORRECT_L,
#         box_size=10,
#         border=4,
#     )
#     qr.add_data(data)
#     qr.make(fit=True)
#     img = qr.make_image(fill="black", back_color="white")
#     if not os.path.exists(directory):
#         os.makedirs(directory)
#     qr_code_filename = f"id_{str(id)}_qrcode.png"
#     qr_code_path = os.path.join(directory, qr_code_filename)
#     with open(qr_code_path, "wb") as file:
#         img.save(file)
#     return qr_code_filename  # 只返回文件名，而不是完整路径


def save_file(file: UploadFile, directory: str, file_type: str,
              id: str) -> Optional[str]:
    """
    Save the uploaded file to the specified directory with a unique filename
    that includes the file type, id, and a unique identifier.
    Return the file path.
    """
    if not file:
        return None

    # Create the specific directory for the file type if it doesn't exist
    specific_directory = os.path.join(directory, file_type)
    if not os.path.exists(specific_directory):
        os.makedirs(specific_directory)

    _, ext = os.path.splitext(file.filename)
    unique_identifier = str(uuid.uuid4())
    unique_filename = f"id_{id}_{file_type}_{unique_identifier}{ext}"
    file_path = os.path.join(specific_directory, unique_filename)

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file.file.read())
    except IOError:
        return None

    return file_path


@dataclass
class EmailData:
    html_content: str
    subject: str


def render_email_template(*, template_name: str, context: dict[str,
                                                               Any]) -> str:
    template_str = (Path(__file__).parent / "email-templates" / "build" /
                    template_name).read_text()
    html_content = Template(template_str).render(context)
    return html_content


def send_email(
    *,
    email_to: str,
    subject: str = "",
    html_content: str = "",
) -> None:
    assert settings.emails_enabled, "no provided configuration for email variables"
    message = emails.Message(
        subject=subject,
        html=html_content,
        mail_from=(settings.EMAILS_FROM_NAME, settings.EMAILS_FROM_EMAIL),
    )
    smtp_options = {"host": settings.SMTP_HOST, "port": settings.SMTP_PORT}
    if settings.SMTP_TLS:
        smtp_options["tls"] = True
    elif settings.SMTP_SSL:
        smtp_options["ssl"] = True
    if settings.SMTP_USER:
        smtp_options["user"] = settings.SMTP_USER
    if settings.SMTP_PASSWORD:
        smtp_options["password"] = settings.SMTP_PASSWORD
    response = message.send(to=email_to, smtp=smtp_options)
    logging.info(f"send email result: {response}")


def generate_test_email(email_to: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Test email"
    html_content = render_email_template(
        template_name="test_email.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "email": email_to
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_reset_password_email(email_to: str, email: str,
                                  token: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Password recovery for user {email}"
    link = f"{settings.server_host}/reset-password?token={token}"
    html_content = render_email_template(
        template_name="reset_password.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": email,
            "email": email_to,
            "valid_hours": settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
            "link": link,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_new_account_email(email_to: str, username: str,
                               password: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - New account for user {username}"
    html_content = render_email_template(
        template_name="new_account.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": username,
            "password": password,
            "email": email_to,
            "link": settings.server_host,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_password_reset_token(email: str) -> str:
    delta = timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS)
    now = datetime.utcnow()
    expires = now + delta
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {
            "exp": exp,
            "nbf": now,
            "sub": email
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    return encoded_jwt


def verify_password_reset_token(token: str) -> str | None:
    try:
        decoded_token = jwt.decode(token,
                                   settings.SECRET_KEY,
                                   algorithms=["HS256"])
        return str(decoded_token["sub"])
    except JWTError:
        return None
