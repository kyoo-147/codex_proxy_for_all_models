from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)


def load_font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates: Iterable[str]
    if mono:
        candidates = (
            "C:/Windows/Fonts/consola.ttf",
            "C:/Windows/Fonts/Consola.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/System/Library/Fonts/SFNSMono.ttf",
        )
    else:
        candidates = (
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        )

    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


TITLE_FONT = load_font(58)
SUBTITLE_FONT = load_font(26)
LABEL_FONT = load_font(22)
MONO_FONT = load_font(26, mono=True)
SMALL_MONO_FONT = load_font(20, mono=True)
FEATURE_TEXT_FONT = load_font(18)


def gradient_background(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, "#0a1020")
    draw = ImageDraw.Draw(image)

    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(8 + 20 * ratio)
        g = int(16 + 32 * ratio)
        b = int(32 + 68 * ratio)
        draw.line((0, y, width, y), fill=(r, g, b))

    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((-120, -40, 460, 520), fill=(0, 209, 255, 48))
    glow_draw.ellipse((width - 480, 40, width + 140, 620), fill=(119, 91, 255, 50))
    glow_draw.ellipse((220, height - 260, 920, height + 180), fill=(53, 214, 143, 34))
    return Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")


def rounded_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str) -> None:
    draw.rounded_rectangle(box, radius=28, fill=fill, outline=outline, width=2)


def draw_hero() -> None:
    image = gradient_background((1280, 720))
    draw = ImageDraw.Draw(image)

    rounded_panel(draw, (72, 80, 1208, 640), "#0d1529", "#24324f")
    draw.text((118, 128), "Codex Proxy for All Models", font=TITLE_FONT, fill="#f4f7fb")
    draw.text(
        (120, 208),
        "Codex-first lightweight model bridge for NVIDIA NIM\n"
        "and other OpenAI-compatible backends.",
        font=SUBTITLE_FONT,
        fill="#b8c4d9",
        spacing=10,
    )

    feature_boxes = [
        ((118, 340, 378, 440), "Lightweight", "Pure stdlib. No FastAPI."),
        ((402, 340, 662, 440), "Vendor-agnostic", "Swap upstream by env."),
        ((686, 340, 946, 440), "Codex-ready", "Responses -> chat API."),
        ((970, 340, 1170, 440), "Cross-platform", "Win, macOS, Linux."),
    ]
    for box, title, text in feature_boxes:
        rounded_panel(draw, box, "#101c34", "#263555")
        draw.text((box[0] + 18, box[1] + 18), title, font=LABEL_FONT, fill="#f6f8fc")
        draw.text((box[0] + 18, box[1] + 58), text, font=FEATURE_TEXT_FONT, fill="#9cb0ce")

    terminal = (120, 486, 1160, 598)
    rounded_panel(draw, terminal, "#06101f", "#1d2f50")
    draw.text((144, 510), "$ python -m codex_proxy_for_all_models", font=MONO_FONT, fill="#8ef0ff")
    draw.text((144, 550), "[proxy] listening on http://127.0.0.1:8787 -> z-ai/glm-5.2", font=SMALL_MONO_FONT, fill="#d7e3f5")

    image.save(ASSETS / "hero.png", optimize=True)


def frame(command: str, body: list[str], footer: str) -> Image.Image:
    image = gradient_background((1280, 720))
    draw = ImageDraw.Draw(image)

    rounded_panel(draw, (70, 70, 1210, 650), "#0d1529", "#24324f")
    draw.text((118, 118), "Quick Demo", font=TITLE_FONT, fill="#f4f7fb")
    draw.text((120, 194), "Codex custom model flow through local proxy", font=SUBTITLE_FONT, fill="#b9c6dd")

    rounded_panel(draw, (120, 270, 1160, 590), "#06101f", "#1d2f50")
    draw.text((148, 300), command, font=MONO_FONT, fill="#8ef0ff")

    y = 360
    for line in body:
        draw.text((148, y), line, font=SMALL_MONO_FONT, fill="#dce7f7")
        y += 38

    draw.text((120, 622), footer, font=LABEL_FONT, fill="#76e3b0")
    return image


def draw_demo() -> None:
    frames = [
        frame(
            "$ export CODEX_PROXY_UPSTREAM_BASE_URL=https://integrate.api.nvidia.com/v1",
            [
                "$ export CODEX_PROXY_UPSTREAM_MODEL=z-ai/glm-5.2",
                "$ python -m codex_proxy_for_all_models",
                "[proxy] listening on http://127.0.0.1:8787",
            ],
            "1. Point proxy at any OpenAI-compatible chat/completions backend",
        ),
        frame(
            "$ curl http://127.0.0.1:8787/v1/models",
            [
                "{",
                '  "data": [{"id": "z-ai/glm-5.2", "owned_by": "NVIDIA Build"}]',
                "}",
            ],
            "2. Codex sees model catalog through Responses-compatible surface",
        ),
        frame(
            "$ codex",
            [
                "Model: Custom Medium",
                "Task: Build small Python web app",
                "Result: proxy forwards chat/completions upstream",
            ],
            "3. Keep Codex UX, swap backend freely",
        ),
    ]

    first, *rest = [frame.convert("P", palette=Image.ADAPTIVE) for frame in frames]
    first.save(
        ASSETS / "demo.gif",
        save_all=True,
        append_images=rest,
        duration=[1400, 1400, 1600],
        loop=0,
        optimize=False,
    )


def draw_social_preview(output_path: Path, title: str, subtitle: str) -> None:
    image = gradient_background((1280, 640))
    draw = ImageDraw.Draw(image)
    rounded_panel(draw, (64, 64, 1216, 576), "#0d1529", "#24324f")
    draw.text((112, 128), title, font=TITLE_FONT, fill="#f4f7fb")
    draw.text((112, 226), subtitle, font=SUBTITLE_FONT, fill="#b8c4d9", spacing=8)
    image.save(output_path, optimize=True)


if __name__ == "__main__":
    draw_hero()
    draw_demo()
    draw_social_preview(
        ASSETS / "social-preview-github.png",
        "Codex Proxy for All Models",
        "Codex-first lightweight model bridge\nfor NVIDIA NIM and OpenAI-compatible backends.",
    )
    draw_social_preview(
        ASSETS / "social-preview-og.png",
        "Codex Pool Router v0.2",
        "Curated Codex profiles with automatic failover,\nmulti-key rotation, and cooldown.",
    )
