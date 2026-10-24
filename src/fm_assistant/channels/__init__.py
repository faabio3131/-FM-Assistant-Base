"""Adapters de canais externos do FM Assistant Base."""

from .whatsapp_meta import (
    AudioTranscriptionUnavailable,
    MetaWhatsAppClient,
    WhatsAppDeliveryUncertain,
    WhatsAppInboundMessage,
    WhatsAppMetaConfig,
    WhatsAppProviderError,
)

__all__ = [
    "AudioTranscriptionUnavailable",
    "MetaWhatsAppClient",
    "WhatsAppDeliveryUncertain",
    "WhatsAppInboundMessage",
    "WhatsAppMetaConfig",
    "WhatsAppProviderError",
]
