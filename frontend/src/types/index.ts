export interface Message {
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: string;
    is_html?: boolean; 
  }