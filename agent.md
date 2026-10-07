# Briefin - AI Agent Context & System Architecture

## 🤖 Introduction
This document serves as a comprehensive reference for AI agents (and human developers) working on the **Briefin** project. It outlines the project's architecture, recent updates (especially the WhatsApp Gateway optimizations), and rules for modifying the codebase.

---

## 🎯 Project Overview
**Briefin** is a fully autonomous daily market brief generator for the Indonesian Stock Exchange (IDX). It fetches data using the **Sectors Financial API (v2)**, summarizes it using AI (Google Gemini / Anthropic Claude), and broadcasts the brief as text + an infographic card to users via **WhatsApp (Baileys/Fonnte)** and **Telegram**.

It is designed to be triggered via GitHub Actions cron job every weekday at 06:30 WIB.

---

## 🏗️ Architecture & Core Components

### 1. Python Backend (`/src`)
Handles data fetching, normalization, AI summarization, image generation, and dispatching.
- **`main.py`**: The entry point. Manages the high-level workflow pipeline (Fetch -> Normalize -> Image -> AI Summary -> Dispatch).
- **`fetch_sectors.py`**: Interacts with the Sectors API to get total market cap, IHSG movement, and top gainers/losers.
- **`format_brief.py`**: Formats the raw JSON data and contains a fallback template engine in case the AI APIs fail.
- **`summarize_ai.py`**: Handles prompts and interaction with Google Gemini (1.5 Flash) and Anthropic Claude (3.5 Sonnet).
- **`generate_card.py`**: Generates a `.png` infographic market card.
- **`send_whatsapp.py` & `send_telegram.py`**: Push the final message and image to the respective channels. `send_whatsapp.py` intelligently falls back to Fonnte if the self-hosted local gateway isn't used.

### 2. WhatsApp Gateway Node.js App (`/wa-gateway`)
A self-hosted WhatsApp gateway built using **@whiskeysockets/baileys** and **Express.js**.
- **`server.js`**: 
  - Manages the Baileys socket connection and QR code pairing.
  - Exposes HTTP REST API endpoints (`/send`, `/subscribers`, `/status`) for the Python backend to use.
  - Implements an interactive auto-responder for WhatsApp users to subscribe/unsubscribe via chat commands (`!daftar`, `!batal`, `!info`).
  - Contains robust JID (WhatsApp ID) formatting, target parsing, and deduplication logic.
- **`db.js`**: 
  - Manages subscriber data sync to **Supabase**.
  - Provides a **graceful fallback** to a local JSON file (`subscribers.json`) if Supabase is down or not configured.

---

## 🔄 Recent Major Updates (Context)

An update was recently merged which introduced advanced WhatsApp handling and database synchronization:

1. **Supabase Integration**:
   - Subscriber persistence was upgraded to use Supabase (`is_active`, `phone`, `jid`).
   - The local `subscribers.json` now acts as a reliable offline backup/fallback mechanism.
2. **Robust WhatsApp Number/Target Normalization**:
   - `server.js` now strictly parses and normalizes raw targets (e.g., `0812...`, `+6281...`) to standardized JIDs (`@s.whatsapp.net`).
   - Supports and correctly identifies Group JIDs (`@g.us`) and Linked Identities (`@lid`).
3. **Deduplication Engine**:
   - Prevented users from receiving double broadcasts by implementing a recursive target deduplication logic in `parseTargets(input)`.
4. **Baileys Log Suppression**:
   - Overrides standard `console.info` to filter out overly verbose/noisy internal `libsignal` session closures from Baileys, keeping the console output clean and readable.
5. **WhatsApp Verification Check**:
   - Utilizes `sock.onWhatsApp(destJid)` to ensure numbers are actually registered on WhatsApp before attempting delivery, reducing unhandled send errors.
6. **Custom Topic Preferences & 9 Market Topics**:
   - Subscribers can customize their daily brief topics via `!topik` (WhatsApp) and `/topik` (Telegram).
   - Available topics: `ihsg`, `gainers`, `losers`, `sektor`, `asing`, `makro`, `ipo`, `watchlist`, `berita`.
   - Fallback template and AI JSON prompt both support pure structured outputs across all 9 topics.
7. **Instant Manual Trigger (`!briefin`)**:
   - Allows users/groups to request their tailored brief immediately on-demand via WhatsApp.
   - Powered by smart 4-hour local caching (`logs/cached_normalized.json` & `logs/cached_summary.json`) so on-demand triggers do not waste Sectors API credits and respond within 1-2 seconds.
8. **Multi-Style Infographic Cards (`!kartu` / `generate_card.py`)**:
   - **Versi 1 (Standard)**: IHSG Composite Pulse + Top 5 Gainers & Losers (Angka IHSG komposit putih bersih).
   - **Versi 2 (Sector & Macro)**: IDX Sector Heatmap + Global Macro (Minyak, Emas, CPO) & Technical Watchlist.
   - **Versi 3 (Executive All-in-One)**: 3-Column Dashboard Lengkap (IHSG, Gainers/Losers, Sektor, & Watchlist).
   - Subscribers can switch design anytime using `!kartu 1`, `!kartu 2`, or `!kartu 3`.

---

## 🛠️ Tech Stack & Environment Variables

### Tech Stack
- **Python 3.11+**: Workflow automation, API integrations.
- **Node.js (Express)**: WhatsApp Baileys gateway.
- **Supabase**: Primary database for subscriber states.
- **GitHub Actions**: Cron scheduling and artifact logging.

### Key Environment Variables (`.env`)
- `SECTORS_API_KEY`: Required for fetching market data.
- `GEMINI_API_KEY` / `ANTHROPIC_API_KEY`: AI summarization.
- `WA_GATEWAY_URL`: e.g., `http://localhost:3000` for local Baileys gateway.
- `SUPABASE_URL` / `SUPABASE_KEY`: Database config for the WA gateway.
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`: For Telegram broadcasts.

---

## 📋 Rules for AI Agents modifying this codebase
1. **Graceful Fallbacks**: If you modify the Supabase integration or the AI summarization, ALWAYS ensure the local JSON fallback and the template-based fallback continue to function flawlessly. Reliability is key since this is an automated cron job.
2. **Baileys Gateway Changes**: When editing `server.js`, keep target deduplication intact. Never remove the `.endsWith('@s.whatsapp.net')` and `@g.us` conditional checks because Baileys handles different JID types strictly differently.
3. **Environment Agnostic**: The Python scripts must run successfully locally as well as in GitHub Actions without modifying the code. Rely purely on the presence of Environment Variables.
4. **Logging**: Maintain robust error handling and logging (`logger.info`, `logger.error`), as cron jobs run invisibly.

---
*Generated by Antigravity AI to assist future agentic operations and developer context.*
