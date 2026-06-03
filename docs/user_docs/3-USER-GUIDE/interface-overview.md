# Interface Overview - Finding Your Way Around

Lumina·Omax uses a clean three-panel layout with multi-user authentication. This guide shows you where everything is.

## Sources Page (Global View)

Access via navigation bar → Sources. This page lists all uploaded sources across all notebooks in a table view:

```
┌───────────────────────────────────────────────────────────┐
│  All Sources                                              │
├──────────┬──────────┬──────────┬──────────┬──────────────┤
│  Title   │ Notebook │ Uploader │ Created  │ Actions      │
├──────────┼──────────┼──────────┼──────────┼──────────────┤
│  Paper   │ Research │ Alice    │ 2026-01 │ [Open] [Del] │
│  Data    │ Lab A    │ Bob      │ 2026-02 │ [Open] [Del] │
│  Report  │ Project  │ Alice    │ 2026-03 │ [Open] [Del] │
└──────────┴──────────┴──────────┴──────────┴──────────────┘
```

- **Uploader column** shows who uploaded each source, helping teams track data provenance
- Supports sorting and pagination (30 sources per page)

---


Lumina·Omax requires each user to log in with their own account.

### First Visit

When you first open the application, you will see the **Landing Page** featuring:

- **Left Panel** — Product introduction, core R&D methodology (7-step closed loop, formula-to-condition mapping, failure case accumulation, mechanism prediction), key metrics
- **Right Panel** — Login / Registration forms

### Register a New Account

1. Click the **Register** tab on the login page
2. Fill in: **Username**, **Display Name**, **Password** (minimum 6 characters)
3. Click **Register**
4. Your account will be created with **pending** status
5. An administrator must approve your account before you can log in

### Login

1. Enter your **Username** and **Password**
2. Click **Login**
3. If you are the system administrator, you may also use the deployment password to bypass login

After successful login, you will be redirected to the main notebooks workspace.



## The Main Layout

```
┌─────────────────────────────────────────────────────────────┐
│  [Logo]  Notebooks  Search  Podcasts  Models  Settings      │
├──────────────┬──────────────┬───────────────────────────────┤
│              │              │                               │
│   SOURCES    │    NOTES     │           CHAT                │
│              │              │                               │
│  Your docs   │  Your        │   Talk to AI about            │
│  PDFs, URLs  │  insights    │   your sources                │
│  Videos      │  summaries   │                               │
│              │              │                               │
│  [+Add]      │  [+Write]    │   [Type here...]              │
│              │              │                               │
└──────────────┴──────────────┴───────────────────────────────┘
```

---

## Navigation Bar

The top navigation takes you to main sections:

| Icon | Page | What It Does |
|------|------|--------------|
| **Notebooks** | Main workspace | Your research projects |
| **Search** | Ask & Search | Query across all notebooks |
| **Podcasts** | Audio generation | Manage podcast profiles |
| **Models** | AI configuration | Set up providers and models |
| **Settings** | Preferences | App configuration |

---

## Left Panel: Sources

Your research materials live here.

### What You'll See

```
┌─────────────────────────┐
│  Sources (5)            │
│  [+ Add Source]         │
├─────────────────────────┤
│  ┌─────────────────┐    │
│  │ 📄 Paper.pdf    │    │
│  │ 🟢 Full Content │    │
│  │ [⋮ Menu]        │    │
│  └─────────────────┘    │
│                         │
│  ┌─────────────────┐    │
│  │ 🔗 Article URL  │    │
│  │ 🟡 Summary Only │    │
│  │ [⋮ Menu]        │    │
│  └─────────────────┘    │
└─────────────────────────┘
```

### Source Card Elements

- **Icon** - File type (PDF, URL, video, etc.)
- **Title** - Document name
- **Context indicator** - What AI can see:
  - 🟢 Full Content
  - 🟡 Summary Only
  - ⛔ Not in Context
- **Menu (⋮)** - Edit, transform, delete

### Add Source Button

Click to add:
- File upload (PDF, DOCX, etc.)
- Web URL
- YouTube video
- Plain text

---

## Middle Panel: Notes

Your insights and AI-generated content.

### What You'll See

```
┌─────────────────────────┐
│  Notes (3)              │
│  [+ Write Note]         │
├─────────────────────────┤
│  ┌─────────────────┐    │
│  │ 📝 My Analysis  │    │
│  │ Manual note     │    │
│  │ Jan 3, 2026     │    │
│  └─────────────────┘    │
│                         │
│  ┌─────────────────┐    │
│  │ 🤖 Summary      │    │
│  │ From transform  │    │
│  │ Jan 2, 2026     │    │
│  └─────────────────┘    │
└─────────────────────────┘
```

### Note Card Elements

- **Icon** - Note type (manual 📝 or AI 🤖)
- **Title** - Note name
- **Origin** - How it was created
- **Date** - When created

### Write Note Button

Click to:
- Create manual note
- Add your own insights
- Markdown supported

---

## Right Panel: Chat

Your AI conversation space.

### What You'll See

```
┌───────────────────────────────┐
│  Chat                         │
│  Session: Research Discussion │
│  [+ New Session] [Sessions ▼] │
├───────────────────────────────┤
│                               │
│  You: What's the main         │
│       finding?                │
│                               │
│  AI: Based on the paper [1],  │
│      the main finding is...   │
│      [Save as Note]           │
│                               │
│  You: Tell me more about      │
│       the methodology.        │
│                               │
├───────────────────────────────┤
│  Context: 3 sources (12K tok) │
├───────────────────────────────┤
│  [Type your message...]  [↑]  │
└───────────────────────────────┘
```

### Chat Elements

- **Session selector** - Switch between conversations
- **Message history** - Your conversation
- **Save as Note** - Keep good responses
- **Context indicator** - What AI can see
- **Input field** - Type your questions

---

## Context Indicators

These show what AI can access:

### Token Counter

```
Context: 3 sources (12,450 tokens)
         ↑          ↑
         Sources    Approximate cost indicator
         included
```

### Per-Source Indicators

| Indicator | Meaning | AI Access |
|-----------|---------|-----------|
| 🟢 Full Content | Complete text | Everything |
| 🟡 Summary Only | AI summary | Key points only |
| ⛔ Not in Context | Excluded | Nothing |

Click any source to change its context level.

---

## Podcasts Tab

Inside a notebook, switch to Podcasts:

```
┌───────────────────────────────┐
│  [Chat]  [Podcasts]           │
├───────────────────────────────┤
│  Episode Profile: [Select ▼]  │
│                               │
│  Speakers:                    │
│  ├─ Host: Alex (voice model)  │
│  └─ Guest: Sam (voice model)  │
│                               │
│  Include:                     │
│  ☑ Paper.pdf                  │
│  ☑ My Analysis (note)         │
│  ☐ Background article         │
│                               │
│  [Generate Podcast]           │
└───────────────────────────────┘
```

---

## Settings Page

Access via navigation bar → Settings:

### Key Sections

| Section | What It Controls |
|---------|------------------|
| **Processing** | Document and URL extraction engines |
| **Embedding** | Auto-embed settings |
| **Files** | Auto-delete uploads after processing |
| **YouTube** | Preferred transcript languages |
| **User Approval Dashboard** | (Admin only) Approve/reject registrations, manage roles, reset passwords |

### User Approval Dashboard (Admin Only)

Administrators can see the **User Approval Dashboard** at the bottom of the Settings page:

```
┌───────────────────────────────────────────────────────┐
│  User Registration Approval & Account Management     │
├───────────────────────────────────────────────────────┤
│  [All (5)] [Pending (2)] [Active (2)] [Rejected (1)] │
├───────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────┐  │
│  │  Zhang San      @zhangsan    [Admin ▼]         │  │
│  │  Registered: 2026-05-15                         │  │
│  │  Status: Active     [Disable]  [Reset Password] │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────┐  │
│  │  Li Si          @lisi        [User ▼]           │  │
│  │  Registered: 2026-05-20                         │  │
│  │  Status: Pending    [Approve]  [Reject]         │  │
│  └─────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────┘
```

Administrators can:
- **Approve** pending registrations (user becomes active)
- **Reject** pending applications
- **Disable** active accounts
- **Toggle role** between User ↔ Admin (click the role badge)
- **Reset password** for any active user (opens a secure dialog with password confirmation)

---

## Models Page

Configure AI providers:

```
┌───────────────────────────────────────┐
│  Models                               │
├───────────────────────────────────────┤
│  Language Models                      │
│  ┌─────────────────────────────────┐  │
│  │ GPT-4o (OpenAI)         [Edit]  │  │
│  │ Claude Sonnet (Anthropic)       │  │
│  │ Llama 3.3 (Ollama)      [⭐]    │  │
│  └─────────────────────────────────┘  │
│  [+ Add Model]                        │
│                                       │
│  Embedding Models                     │
│  ┌─────────────────────────────────┐  │
│  │ text-embedding-3-small  [⭐]    │  │
│  └─────────────────────────────────┘  │
│                                       │
│  Text-to-Speech                       │
│  ┌─────────────────────────────────┐  │
│  │ OpenAI TTS             [⭐]     │  │
│  │ Google TTS                      │  │
│  └─────────────────────────────────┘  │
└───────────────────────────────────────┘
```

- **⭐** = Default model for that category
- **[Edit]** = Modify configuration
- **[+ Add]** = Add new model

---

## Search Page

Query across all notebooks:

```
┌───────────────────────────────────────┐
│  Search                               │
├───────────────────────────────────────┤
│  [What are you looking for?    ] [🔍] │
│                                       │
│  Search type: [Text ▼] [Vector ▼]     │
│  Search in:   [Sources] [Notes]       │
├───────────────────────────────────────┤
│  Results (15)                         │
│                                       │
│  📄 Paper.pdf - Notebook: Research    │
│     "...the transformer model..."     │
│                                       │
│  📝 My Analysis - Notebook: Research  │
│     "...key findings include..."      │
└───────────────────────────────────────┘
```

---

## Common Actions

### Create a Notebook

```
Notebooks page → [+ New Notebook] → Enter name → Create
```

### Add a Source

```
Inside notebook → [+ Add Source] → Choose type → Upload/paste → Wait for processing
```

### Ask a Question

```
Inside notebook → Chat panel → Type question → Enter → Read response
```

### Save AI Response

```
Get good response → Click [Save as Note] → Edit title → Save
```

### Change Context Level

```
Click source → Context dropdown → Select level → Changes apply immediately
```

### Generate Podcast

```
Podcasts tab → Select profile → Choose sources → [Generate] → Wait → Download
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Send chat message |
| `Shift + Enter` | New line in chat |
| `Escape` | Close dialogs |
| `Ctrl/Cmd + F` | Browser find |

---

## Mobile View

On smaller screens, the three-panel layout stacks vertically:

```
┌─────────────────┐
│    SOURCES      │
│    (tap to expand)
├─────────────────┤
│    NOTES        │
│    (tap to expand)
├─────────────────┤
│    CHAT         │
│    (always visible)
└─────────────────┘
```

- Panels collapse to save space
- Tap headers to expand/collapse
- Chat remains accessible
- Full functionality preserved

---

## Tips for Efficient Navigation

1. **Use keyboard** - Enter sends messages, Escape closes dialogs
2. **Context first** - Set source context before chatting
3. **Sessions** - Create new sessions for different topics
4. **Search globally** - Use Search page to find across all notebooks
5. **Models page** - Bookmark your preferred models
6. **Check uploader** - Hover over source cards to see who uploaded each file
7. **Admin tasks** - Administrators can manage users from Settings → scroll to the bottom

---

Now you know where everything is. Start with [Adding Sources](adding-sources.md) to begin your research!
