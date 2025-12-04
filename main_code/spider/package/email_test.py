#!/usr/bin/env python3
"""
Utility script for sending a test email to verify SMTP credentials.

Example:
    python3 -m spider.package.email_test --username xxx@qq.com --password app_code
    python3 -m spider.package.email_test --username xxx@qq.com --password app_code \
        --attachment ~/Desktop/result.xlsx
"""

from __future__ import annotations

import argparse
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from paths import EMAIL_TEST_LOG
from spider.package.core.logger_manager import LoggerManager

DEFAULT_RECIPIENT = "2848083644@qq.com"
DEFAULT_SUBJECT = "Run5 邮件发送测试"
DEFAULT_BODY = (
    "这是一封由 run5-server 自动化脚本发送的测试邮件。\n"
    "如果你能看到这封邮件，说明 SMTP 配置正常。"
)
TRANSPORT_CHOICES = ("ssl", "starttls", "plain")


def _env_default(key: str, fallback: str) -> str:
    value = os.environ.get(key, fallback)
    return value.strip() or fallback


class EmailTester:
    """Small helper for sending SMTP messages with logging."""

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        transport: str = "ssl",
        timeout: int = 15,
        sender_name: Optional[str] = None,
    ) -> None:
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.transport = transport if transport in TRANSPORT_CHOICES else "ssl"
        self.timeout = timeout
        self.sender_name = sender_name or username
        self.logger = LoggerManager.setup_logger("email_test", str(EMAIL_TEST_LOG))

    def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        attachments: Optional[Sequence[Path]] = None,
    ) -> bool:
        if not self.username or not self.password:
            self.logger.error("SMTP 用户名或密码未提供，无法发送邮件")
            return False

        try:
            message = self._build_message(
                recipient=recipient,
                subject=subject,
                body=body,
                attachments=attachments or [],
            )
        except OSError as exc:
            self.logger.error("加载附件失败：%s", exc)
            return False

        try:
            client = self._connect()
            with client:
                client.login(self.username, self.password)
                client.sendmail(self.username, [recipient], message.as_string())
            self.logger.info("测试邮件发送成功 -> %s", recipient)
            return True
        except smtplib.SMTPAuthenticationError as exc:
            self.logger.error("SMTP 认证失败：%s", exc)
        except smtplib.SMTPException as exc:
            self.logger.error("发送邮件失败：%s", exc)
        except OSError as exc:
            self.logger.error("SMTP 连接异常：%s", exc)
        return False

    def _connect(self) -> smtplib.SMTP:
        if self.transport == "ssl":
            self.logger.debug(
                "使用 SSL 连接 %s:%s 发送邮件", self.smtp_server, self.smtp_port
            )
            return smtplib.SMTP_SSL(
                host=self.smtp_server, port=self.smtp_port, timeout=self.timeout
            )

        self.logger.debug(
            "使用普通 SMTP 连接 %s:%s (transport=%s)",
            self.smtp_server,
            self.smtp_port,
            self.transport,
        )
        client = smtplib.SMTP(
            host=self.smtp_server, port=self.smtp_port, timeout=self.timeout
        )
        if self.transport == "starttls":
            client.starttls()
        return client

    def _build_message(
        self,
        recipient: str,
        subject: str,
        body: str,
        attachments: Sequence[Path],
    ) -> MIMEText:
        files = [path for path in attachments if path]
        if files:
            message = MIMEMultipart()
            message.attach(MIMEText(body, "plain", "utf-8"))
            for file_path in files:
                payload = file_path.read_bytes()
                part = MIMEApplication(payload)
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=file_path.name,
                )
                message.attach(part)
        else:
            message = MIMEText(body, "plain", "utf-8")

        message["Subject"] = subject
        message["From"] = formataddr((self.sender_name, self.username))
        message["To"] = recipient
        if files:
            self.logger.info("即将发送带 %d 个附件的测试邮件", len(files))
        return message


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="向 2848083644@qq.com 发送测试邮件，验证 SMTP 配置是否正确。"
    )
    parser.add_argument(
        "--smtp-server",
        default=_env_default("RUN5_SMTP_SERVER", "smtp.qq.com"),
        help="SMTP 服务器地址，默认 smtp.qq.com",
    )
    parser.add_argument(
        "--smtp-port",
        type=int,
        default=int(_env_default("RUN5_SMTP_PORT", "465")),
        help="SMTP 端口，默认 465",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("RUN5_SMTP_USERNAME", ""),
        help="SMTP 登录账号（通常为邮箱地址）",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("RUN5_SMTP_PASSWORD", ""),
        help="SMTP 登录授权码/密码",
    )
    parser.add_argument(
        "--sender-name",
        default=os.environ.get("RUN5_SMTP_SENDER_NAME", ""),
        help="显示在邮件中的发件人名称",
    )
    parser.add_argument(
        "--recipient",
        default=DEFAULT_RECIPIENT,
        help="收件人邮箱，默认 2848083644@qq.com",
    )
    parser.add_argument(
        "--subject",
        default=_env_default("RUN5_SMTP_SUBJECT", DEFAULT_SUBJECT),
        help="测试邮件主题",
    )
    parser.add_argument(
        "--body",
        default=os.environ.get("RUN5_SMTP_BODY", DEFAULT_BODY),
        help="测试邮件正文",
    )
    parser.add_argument(
        "--body-file",
        type=str,
        default="",
        help="可选，读取文件内容作为邮件正文",
    )
    parser.add_argument(
        "--transport",
        choices=TRANSPORT_CHOICES,
        default=_env_default("RUN5_SMTP_TRANSPORT", "ssl"),
        help="SMTP 连接方式：ssl、starttls 或 plain",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(_env_default("RUN5_SMTP_TIMEOUT", "15")),
        help="网络超时时间，单位秒，默认 15",
    )
    parser.add_argument(
        "--attachment",
        action="append",
        default=[],
        metavar="FILE",
        help="可选，添加一个附件，可重复多次指定",
    )
    return parser


def load_body_text(body_arg: str, body_file: str) -> str:
    if body_file:
        file_path = Path(body_file).expanduser()
        content = file_path.read_text(encoding="utf-8")
        return content.strip() or body_arg
    return body_arg


def resolve_attachments(files: Iterable[str]) -> List[Path]:
    attachments: List[Path] = []
    for raw in files:
        if not raw:
            continue
        file_path = Path(raw).expanduser()
        if not file_path.is_file():
            raise FileNotFoundError(f"附件不存在：{file_path}")
        attachments.append(file_path)
    return attachments


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    body_text = load_body_text(args.body, args.body_file)
    attachments: Sequence[Path] = []
    tester = EmailTester(
        smtp_server=args.smtp_server,
        smtp_port=args.smtp_port,
        username=args.username,
        password=args.password,
        transport=args.transport,
        timeout=args.timeout,
        sender_name=args.sender_name or args.username,
    )

    try:
        attachments = resolve_attachments(args.attachment)
    except FileNotFoundError as exc:
        tester.logger.error(str(exc))
        return 1

    success = tester.send(
        recipient=args.recipient,
        subject=args.subject,
        body=body_text,
        attachments=attachments,
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
