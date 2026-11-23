"""Pure fingerprint availability policy; unavailable always means password-only."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FingerprintState:
    allowed: bool
    message: str = ''


def availability(*, mode, closed, sleeping, resuming, inhibited, reader, seen_reader):
    if mode not in ('auto', 'on'):
        return FingerprintState(False)
    if closed:
        return FingerprintState(False, 'Fingerprint paused while the lid is closed' if seen_reader else '')
    if sleeping or resuming:
        return FingerprintState(False, 'Fingerprint paused for sleep/resume' if seen_reader else '')
    if not inhibited:
        return FingerprintState(False, 'Fingerprint unavailable — enter your password' if seen_reader else '')
    if not reader:
        return FingerprintState(False, 'Fingerprint reader unavailable — enter your password' if seen_reader else '')
    return FingerprintState(True)
