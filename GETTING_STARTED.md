# เริ่มต้นใช้งาน Mnema (ภาษาไทย)

> **Mnema** (อ่านว่า *นี-มา* มาจากภาษากรีก μνῆμα แปลว่า "ความจำ")
> คือตัวช่วยให้ AI ของคุณมีความจำระยะยาว แก้ปัญหา context window จำกัด
> ด้วยการเก็บข้อมูลสำคัญไว้ใน vector database แล้วดึงกลับมาใช้เมื่อไหร่ก็ได้

คู่มือนี้เขียนสำหรับ **คนที่ไม่ได้มีพื้นฐานด้านโปรแกรมมาก**
เน้นก๊อปปี้คำสั่งไปวางทีละบรรทัด ทำตามได้เลยไม่ต้องคิดมาก 😊

---

## 📋 สิ่งที่ต้องมีก่อน (แค่ 2 อย่าง)

| อันดับ | โปรแกรม | วิธีติดตั้ง |
|---|---|---|
| 1️⃣ | **Terminal** | มีอยู่แล้วในทุกเครื่อง (macOS: แอพ "Terminal", Windows: ใช้ WSL) |
| 2️⃣ | **git** | macOS: เปิด Terminal แล้วพิมพ์ `git --version` (ถ้าไม่มี ระบบจะถามให้ติดตั้งเอง) |

> 💡 สำหรับ Windows แนะนำให้ติดตั้ง [WSL (Ubuntu)](https://learn.microsoft.com/en-us/windows/wsl/install) ก่อน
> แล้วทำตามคู่มือนี้ใน WSL ได้เลย เพราะ Mnema ทำงานบน Linux/macOS ได้ดีกว่า

---

## 🚀 ขั้นที่ 1: ติดตั้ง Mnema (คำสั่งเดียวจบ)

เปิด **Terminal** แล้วก๊อปปี้คำสั่งข้างล่างนี้ไปวาง แล้วกด Enter:

### macOS / Linux
```bash
curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh | bash
```

### ถ้าอยากดูโค้ดก่อนติดตั้ง (ปลอดภัยกว่า)
```bash
git clone https://github.com/mienetic/mnema
cd mnema
# เปิดไฟล์ scripts/install.sh ดูก่อนได้
bash scripts/install.sh
```

**สคริปต์จะทำให้คุณโดยอัตโนมัติ:**
1. ✅ ติดตั้ง `uv` (ตัวจัดการ Python ที่เร็วและง่าย)
2. ✅ ดาวน์โหลดโค้ด Mnema จาก GitHub
3. ✅ ติดตั้ง dependencies ทั้งหมดให้ (รวมโมเดล embedding ออฟไลน์)
4. ✅ สร้างคำสั่ง `mnema` และ `mnema-update` ให้ใช้บน Terminal
5. ✅ รัน `mnema --doctor` เพื่อตรวจว่าทุกอย่างพร้อม

รอประมาณ 2-5 นาที (ครั้งแรกต้องโหลดโมเดล ~80MB) เมื่อเห็นข้อความ
**"✓ Mnema is installed and ready!"** คือเสร็จแล้ว 🎉

---

## 🧪 ขั้นที่ 2: ทดสอบว่าใช้ได้

พิมพ์คำสั่งนี้ใน Terminal:

```bash
mnema --doctor
```

ถ้าเห็นข้อความแบบนี้คือผ่าน:

```
mnema 0.1.0
backend        = chroma  (~/.mnema-data)
embedding      = local  (all-MiniLM-L6-v2)
transport      = stdio
default_scope  = user:me
decay_half_life= 30.0 days

✓ backend 'chroma' loaded
✓ embedding 'local' loaded (dim=384)

All checks passed — Mnema is ready to serve.
```

---

## 🔌 ขั้นที่ 3: เชื่อม Mnema เข้ากับ AI ของคุณ

Mnema ทำงานเป็น **MCP server** — เลือก AI client ที่คุณใช้ด้านล่าง

### ตัวเลือก A: Claude Desktop

1. เปิดไฟล์ config:
   - **macOS:** เปิดไฟล์ `~/Library/Application Support/Claude/claude_desktop_config.json`
     (พิมพ์ใน Finder: `Cmd+Shift+G` แล้ววาง path ด้านบน)
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - ถ้าไฟล์ไม่มี ให้สร้างใหม่

2. วางเนื้อหานี้ลงไป (ถ้ามี config อื่นอยู่แล้ว ให้เพิ่มส่วน `"mnema"` เข้าไปใน `"mcpServers"`):

```json
{
  "mcpServers": {
    "mnema": {
      "command": "mnema",
      "env": {
        "MNEMA_BACKEND": "chroma",
        "MNEMA_BACKEND_PATH": "~/.mnema-data",
        "MNEMA_EMBEDDING": "local",
        "MNEMA_DEFAULT_SCOPE": "user:me"
      }
    }
  }
}
```

3. **ปิด Claude Desktop แล้วเปิดใหม่** (รีสตาร์ทเสมอ ไม่งั้นจะไม่เห็น Mnema)

4. ทดสอบ — พิมพ์ใน Claude:
   > "Remember that I prefer dark mode and use a Dvorak keyboard layout."

   แล้วปิด Claude ไปทำอย่างอื่น พอกลับมาอีกครั้ง (session ใหม่) ถามว่า:
   > "What do you know about my preferences?"

   Claude ควรจะตอบได้ว่าคุณชอบ dark mode และ Dvorak 🎉

### ตัวเลือก B: ZCode

ดูตัวอย่าง config ได้ที่ `examples/zcode-mcp-config.json`

### ตัวเลือก C: Cursor

1. สร้างไฟล์ `~/.cursor/mcp.json`
2. วางเนื้อหาจาก `examples/cursor-mcp-config.json`

---

## 🔄 ขั้นที่ 4: อัพเดทเป็นเวอร์ชั่นล่าสุด

เมื่อมีอัพเดทใหม่บน GitHub พิมพ์คำสั่งนี้ใน Terminal:

```bash
mnema-update
```

คำสั่งเดียวจบ — ดึงโค้ดใหม่จาก GitHub + ติดตั้ง dependencies ใหม่ + ตรวจสอบให้

> 💡 แนะนำให้อัพเดททุก 1-2 สัปดาห์ หรือเมื่อเห็นประกาศ release ใหม่

---

## 🛠️ เปลี่ยนแปลงการตั้งค่า (ไม่บังคับ)

ทุกอย่างตั้งค่าผ่าน **environment variables** (ตัวแปร environment) สำคัญๆ มี:

| ตัวแปร | ค่า default | คำอธิบาย |
|---|---|---|
| `MNEMA_BACKEND` | `chroma` | ฐานข้อมูลหลังบ้าน: `chroma` (default ง่ายสุด), `qdrant`, `sqlite_vec` |
| `MNEMA_EMBEDDING` | `local` | ตัวแปลงข้อความเป็นเวกเตอร์: `local` (ออฟไลน์), `openai` (ต้องมี API key) |
| `MNEMA_DEFAULT_SCOPE` | `user:me` | scope เริ่มต้นเมื่อ AI เก็บความจำ |
| `MNEMA_DECAY_HALF_LIFE_DAYS` | `30` | ครึ่งชีวิตความจำ (วัน) — เลขน้อย = ลืมเร็ว |

**ตัวอย่าง:** อยากใช้ Qdrant แทน Chroma ก็เพิ่มบรรทัดนี้ใน config ของ client:
```json
"env": {
  "MNEMA_BACKEND": "qdrant",
  "MNEMA_BACKEND_PATH": "~/.mnema-data/qdrant"
}
```

---

## 🗂️ ไฟล์อยู่ที่ไหน?

หลังติดตั้ง Mnema จะสร้างไฟล์เหล่านี้:

| Path | คืออะไร |
|---|---|
| `~/.mnema-src/` | โค้ดต้นฉบับ (clone จาก GitHub) |
| `~/.mnema-data/` | ข้อมูลความจำของคุณ (vector database) — **สำคัญ อย่าลบ** |
| `~/.local/bin/mnema` | ตัวเรียกใช้งาน |
| `~/.local/bin/mnema-update` | ตัวอัพเดท |

> ⚠️ ถ้าลบ `~/.mnema-data/` ความจำทั้งหมดที่ AI เก็บไว้จะหายไป

---

## 🤔 เจอปัญหา?

### พิมพ์ `mnema` แล้วไม่เจอคำสั่ง (command not found)

ปิด Terminal แล้วเปิดใหม่ ถ้ายังไม่ได้ ลองพิมพ์:
```bash
export PATH="$HOME/.local/bin:$PATH"
```
แล้วลอง `mnema --doctor` อีกครั้ง ถ้าได้แล้ว ให้เพิ่มบรรทัดนั้นเข้าไปใน `~/.zshrc` (macOS) หรือ `~/.bashrc` (Linux) ถาวร

### Claude Desktop ไม่เห็น Mnema

- ตรวจว่า path ใน config ถูกต้อง (`mnema` ต้องพิมพ์ใน Terminal แล้วเจอ)
- รีสตาร์ท Claude Desktop หลังแก้ config เสมอ
- ดู log ได้ที่ `~/Library/Logs/Claude/mcp*.log` (macOS)

### `mnema --doctor` ฟ้องว่า embedding failed

อาจเป็นเพราะโหลดโมเดลครั้งแรกไม่สำเร็จ ลอง:
```bash
mnema --doctor
```
อีกครั้ง — ถ้ายังไม่ได้ ลองเปลี่ยนเป็น OpenAI embedding (ต้องมี API key):
```bash
export MNEMA_EMBEDDING=openai
export MNEMA_OPENAI_API_KEY=sk-ใส่keyของคุณ
mnema --doctor
```

### อยากลบทิ้งติดตั้งใหม่

```bash
rm -rf ~/.mnema-src ~/.mnema-data ~/.local/bin/mnema ~/.local/bin/mnema-update
```
แล้วรัน installer ใหม่

---

## 📚 อยากรู้เพิ่มเติม?

- **คู่มือ AI client ทั้งหมด** → [examples/](examples/)
- **วิธีใช้ tools ทั้ง 10 ตัว** → [SKILL.md](SKILL.md)
- **สถาปัตยกรรม** → [docs/architecture.md](docs/architecture.md) (ภาษาอังกฤษ)
- **เลือก backend** → [docs/backends.md](docs/backends.md)
- **ปัญหา/แจ้งบั๊ก** → [เปิด issue ที่ GitHub](https://github.com/mienetic/mnema/issues)

---

<p align="center"><i>มีคำถาม? เปิด issue ได้ที่ GitHub เลย 🙌</i></p>
