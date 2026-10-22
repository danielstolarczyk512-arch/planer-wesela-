"""E-maile HTML: dwie części, escapowanie, brak zasobów zewnętrznych, linki w obu wersjach."""

import re
from email import message_from_bytes

from app.core import mail_templates
from app.core.config import get_settings
from app.core.email import build_message


def sample(**kw):
    return mail_templates.build(
        "Temat <test>",
        heading="Wesele <Ani & Tomka>",
        paragraphs=['Zapraszamy na "wesele" <script>alert(1)</script>'],
        action=("Potwierdź", "https://app.example/rsvp/abc?x=1&y=2"),
        sections=[
            mail_templates.Section("Zadania", ["Zarezerwować salę <teraz>"]),
            mail_templates.Section("Puste"),
        ],
        note="Uwaga końcowa",
        **kw,
    )


def test_text_and_html_carry_the_same_content():
    m = sample()
    for part in (m.text, m.html):
        assert "rsvp/abc" in part
        assert "Zadania" in part
        assert "Uwaga końcowa" in part
    assert "Puste" not in m.text  # pusta sekcja pominięta
    assert "Puste" not in m.html
    assert f"{get_settings().public_app_url}/ustawienia" in m.text
    assert "Zmień powiadomienia" in m.html


def test_html_escapes_user_values_and_has_no_external_resources():
    html = sample().html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Wesele &lt;Ani &amp; Tomka&gt;" in html
    assert 'href="https://app.example/rsvp/abc?x=1&amp;y=2"' in html
    assert '<html lang="pl">' in html
    # Bez obrazów, czcionek, arkuszy i skryptów z zewnątrz (prywatność, filtry antyspamowe).
    assert not re.search(r"<(img|link|script|iframe)\b", html, re.I)
    assert "@import" not in html
    assert "url(" not in html


def test_without_settings_link_for_guests():
    m = sample(settings_link=False)
    assert "Zmień powiadomienia" not in m.text
    assert "Zmień powiadomienia" not in m.html


def test_message_is_multipart_alternative_with_plain_text_first():
    m = sample()
    msg = message_from_bytes(
        build_message("ania@example.com", m.subject, m.text, m.html).as_bytes()
    )
    assert msg.get_content_type() == "multipart/alternative"
    parts = [p.get_content_type() for p in msg.walk() if not p.is_multipart()]
    assert parts == ["text/plain", "text/html"]
    # Bez HTML: zwykła wiadomość tekstowa (zgodność wsteczna).
    plain = build_message("ania@example.com", "T", "treść")
    assert plain.get_content_type() == "text/plain"
