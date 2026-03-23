from .ingress import handle_webhook as _handle_webhook

handle_webhook = _handle_webhook

__all__ = ["handle_webhook"]
