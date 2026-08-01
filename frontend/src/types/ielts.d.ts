export type IELTSState =
  | "setup"
  | "part1_intro"
  | "part1_qa"
  | "part2_cue_card"
  | "part2_prep"
  | "part2_speaking"
  | "part2_follow_up"
  | "part3_discussion"
  | "scoring"
  | "complete";

export interface CueCard {
  topic: string;
  bullets: string[];
  theme: string;
}

export interface CurrentPrompt {
  state: IELTSState;
  part?: number | null;
  question?: string | null;
  cue_card?: CueCard | null;
  time_budget_s?: number | null;
  is_final: boolean;
}

export interface IELTSSessionDetail {
  id: string;
  session_id: string;
  status: IELTSState;
  target_band: number;
  topics_preference?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  current_prompt?: CurrentPrompt | null;
  part1_categories?: Record<string, unknown>[] | null;
  part2_cue_card?: CueCard | null;
  part3_questions?: string[] | null;
}

export interface AnswerResult {
  answer_id: string;
  next_prompt: CurrentPrompt;
}

export interface BandDetail {
  band: number;
  justification: string;
  strengths: string[];
  areas_to_improve: string[];
  example_from_response: string;
}

export interface IELTSBandScore {
  fluency_and_coherence: BandDetail;
  lexical_resource: BandDetail;
  grammatical_range_accuracy: BandDetail;
  pronunciation: BandDetail;
  overall_band: number;
}

export interface WordPronunciationScore {
  word: string;
  score: number;
  expected_phonemes: string;
  detected_phonemes: string;
  problem_phonemes: string[];
  timestamp_ms: number;
}

export interface PronunciationAnalysis {
  word_scores: WordPronunciationScore[];
  overall_score: number;
  problem_sounds: string[];
  confidence_caveat: string;
  engine: "wav2vec2" | "heuristic_fallback";
}

export interface PauseEvent {
  start_s: number;
  duration_s: number;
}

export interface PauseAnalysis {
  total_pause_time_s: number;
  avg_pause_duration_s: number;
  long_pauses: PauseEvent[];
  natural_pauses: number;
  unnatural_pauses: number;
}

export interface FillerWord {
  text: string;
  timestamp_s: number;
}

export interface ProsodyAnalysis {
  speaking_rate_wpm: number;
  pace_assessment: "too_fast" | "good" | "too_slow";
  pause_analysis: PauseAnalysis;
  filler_words: FillerWord[];
  filler_ratio: number;
  intonation_variety: number;
}
