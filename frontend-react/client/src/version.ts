/**
 * Versão da aplicação — injetada pelo Vite via `define` em build time.
 *
 * Estes valores são SUBSTITUÍDOS LITERALMENTE no bundle final, ou seja:
 *   APP_VERSION === "1.5.2"   (e não uma referência a process.env)
 *
 * Por que isso importa:
 *   - O bundle gerado tem a versão gravada na própria string de código.
 *   - Diff entre dois bundles compilados muda mesmo que só a versão mude.
 *   - Não dá para "errar" qual versão está rodando.
 *
 * Para usar em runtime:
 *   import { APP_VERSION, GIT_HASH, BUILD_TIME } from "@/version";
 *   console.info(`[MIS Core] ${APP_VERSION} (${GIT_HASH}) — built ${BUILD_TIME}`);
 */

declare const __APP_VERSION__: string;
declare const __GIT_HASH__: string;
declare const __BUILD_TIME__: string;

export const APP_VERSION: string =
  typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "0.0.0-dev";

export const GIT_HASH: string =
  typeof __GIT_HASH__ !== "undefined" ? __GIT_HASH__ : "no-git";

export const BUILD_TIME: string =
  typeof __BUILD_TIME__ !== "undefined" ? __BUILD_TIME__ : "unknown";

/**
 * String para footer / about: "v1.5.2 · ab12cd3 · 2026-04-28T14:08:12Z"
 */
export const FULL_VERSION = `v${APP_VERSION} · ${GIT_HASH} · ${BUILD_TIME}`;

/**
 * Banner de console — chamado uma vez no main.tsx.
 */
export function logVersionBanner(): void {
  /* eslint-disable no-console */
  const style = "color:#3f5b7c; font-weight:600;";
  console.info(
    `%c[MIS Core] running v${APP_VERSION}  ·  ${GIT_HASH}  ·  built ${BUILD_TIME}`,
    style,
  );
  /* eslint-enable no-console */
}
