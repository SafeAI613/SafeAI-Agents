import { useEffect, useState } from "react";
import {
  listFiles, readFile, writeFile, uploadFile, type FileEntry,
} from "../apiTools";

interface Props {
  token: string;
}

/** Workspace file browser: navigate folders, view/edit text files, upload new ones.
 *  Scoped server-side to the files.workspace root (config/default.yaml). */
export function FilesPanel({ token }: Props) {
  const [path, setPath] = useState("");
  const [items, setItems] = useState<FileEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [openFile, setOpenFile] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);

  async function load(p: string) {
    setError(null);
    try {
      setItems(await listFiles(token, p));
      setPath(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : "שגיאה");
    }
  }

  useEffect(() => { load(""); }, []);

  function parentPath(): string {
    const parts = path.split("/").filter(Boolean);
    parts.pop();
    return parts.join("/");
  }

  async function open(entry: FileEntry) {
    if (entry.is_dir) { load(entry.path); return; }
    setError(null);
    try {
      const text = await readFile(token, entry.path);
      setContent(text);
      setOpenFile(entry.path);
      setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "לא ניתן לפתוח");
    }
  }

  async function save() {
    if (!openFile) return;
    setBusy(true);
    try {
      await writeFile(token, openFile, content);
      setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "שמירה נכשלה");
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      await uploadFile(token, file, path);
      await load(path);
    } catch (err) {
      setError(err instanceof Error ? err.message : "העלאה נכשלה");
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  return (
    <div className="panel files-panel" dir="rtl">
      {error && <div className="error-banner">{error}</div>}

      <div className="files-toolbar">
        <span className="path-crumb">/{path}</span>
        <label className="mini-btn upload-btn">
          העלאה
          <input type="file" hidden onChange={onUpload} disabled={busy} />
        </label>
      </div>

      <div className="files-body">
        <ul className="file-list">
          {path && (
            <li className="file-row" onClick={() => load(parentPath())}>
              <span className="file-icon">📁</span> ..
            </li>
          )}
          {items.map((it) => (
            <li
              key={it.path}
              className={`file-row ${openFile === it.path ? "active" : ""}`}
              onClick={() => open(it)}
            >
              <span className="file-icon">{it.is_dir ? "📁" : "📄"}</span>
              <span className="file-name">{it.name}</span>
              {it.size != null && <span className="file-size">{it.size} B</span>}
            </li>
          ))}
          {items.length === 0 && <li className="muted">תיקייה ריקה</li>}
        </ul>

        {openFile && (
          <div className="file-editor">
            <div className="editor-head">
              <code>{openFile}</code>
              <button className="mini-btn" disabled={!dirty || busy} onClick={save}>
                {busy ? "שומר…" : dirty ? "שמור" : "נשמר"}
              </button>
            </div>
            <textarea
              className="editor-area"
              value={content}
              spellCheck={false}
              onChange={(e) => { setContent(e.target.value); setDirty(true); }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
