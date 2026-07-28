/**
 * CodeEditor — Phase 6.
 *
 * Mount point: frontend/src/components/coding/CodeEditor.tsx
 *
 * Wraps @monaco-editor/react with the Poise dark theme and a
 * language/run/submit toolbar. Depends on the design tokens defined
 * in frontend/src/styles/index.css (Phase 1) — swap the CSS var names
 * below if your token names differ.
 *
 * Install (merge into frontend/package.json):
 *   npm install @monaco-editor/react
 */
import { useCallback, useRef, useState } from 'react';
import Editor, { OnMount } from '@monaco-editor/react';
import type { Language, TestCase } from '../../../../contracts/types/coding';

const LANGUAGE_OPTIONS: { value: Language; label: string; monacoId: string }[] = [
  { value: 'python', label: 'Python', monacoId: 'python' },
  { value: 'javascript', label: 'JavaScript', monacoId: 'javascript' },
  { value: 'typescript', label: 'TypeScript', monacoId: 'typescript' },
  { value: 'java', label: 'Java', monacoId: 'java' },
  { value: 'cpp', label: 'C++', monacoId: 'cpp' },
  { value: 'go', label: 'Go', monacoId: 'go' },
  { value: 'rust', label: 'Rust', monacoId: 'rust' },
];

export interface CodeEditorProps {
  language: Language;
  onLanguageChange: (lang: Language) => void;
  starterCode: Record<string, string>;
  testCases?: TestCase[];
  onSubmit: (code: string) => void;
  onRun: (code: string) => void;
  isRunning?: boolean;
  isSubmitting?: boolean;
  readOnly?: boolean;
}

const POISE_DARK_THEME = {
  base: 'vs-dark' as const,
  inherit: true,
  rules: [],
  colors: {
    'editor.background': '#15181f', // matches --color-bg-secondary family
    'editor.lineHighlightBackground': '#1b1f29',
    'editorLineNumber.foreground': '#5c6270',
    'editorCursor.foreground': '#8b7cf6',
  },
};

export function CodeEditor({
  language,
  onLanguageChange,
  starterCode,
  onSubmit,
  onRun,
  isRunning = false,
  isSubmitting = false,
  readOnly = false,
}: CodeEditorProps) {
  const [code, setCode] = useState<string>(starterCode[language] ?? '');
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const currentLanguageRef = useRef(language);

  const handleMount: OnMount = useCallback((editor, monaco) => {
    editorRef.current = editor;
    monaco.editor.defineTheme('poise-dark', POISE_DARK_THEME);
    monaco.editor.setTheme('poise-dark');
  }, []);

  const handleLanguageSwitch = (next: Language) => {
    // Preserve user edits per-language in a lightweight way: only reset
    // to starter code if the user hasn't diverged from the previous
    // language's starter template.
    if (code === (starterCode[currentLanguageRef.current] ?? '')) {
      setCode(starterCode[next] ?? '');
    }
    currentLanguageRef.current = next;
    onLanguageChange(next);
  };

  const monacoLang = LANGUAGE_OPTIONS.find((l) => l.value === language)?.monacoId ?? 'plaintext';

  return (
    <div className="poise-code-editor">
      <div className="poise-code-editor__toolbar">
        <select
          className="poise-code-editor__lang-select"
          value={language}
          onChange={(e) => handleLanguageSwitch(e.target.value as Language)}
          disabled={readOnly}
        >
          {LANGUAGE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        <div className="poise-code-editor__actions">
          <button
            className="poise-btn poise-btn--secondary"
            onClick={() => onRun(code)}
            disabled={isRunning || isSubmitting || readOnly}
          >
            {isRunning ? 'Running…' : '▶ Run'}
          </button>
          <button
            className="poise-btn poise-btn--primary"
            onClick={() => onSubmit(code)}
            disabled={isRunning || isSubmitting || readOnly}
          >
            {isSubmitting ? 'Submitting…' : 'Submit'}
          </button>
        </div>
      </div>

      <Editor
        height="100%"
        language={monacoLang}
        value={code}
        onChange={(value) => setCode(value ?? '')}
        onMount={handleMount}
        theme="poise-dark"
        options={{
          readOnly,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 14,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          automaticLayout: true,
          bracketPairColorization: { enabled: true },
          tabSize: 4,
          wordWrap: 'on',
          quickSuggestions: true,
        }}
      />
    </div>
  );
}
