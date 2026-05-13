/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_DEMO_TEXT_API_KEY?: string;
  readonly VITE_DEMO_IMAGE_API_KEY?: string;
  readonly VITE_DEMO_ADMIN_API_KEY?: string;
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
