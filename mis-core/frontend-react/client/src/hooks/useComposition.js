import { useRef } from "react";
import { usePersistFn } from "./usePersistFn";
export function useComposition(options = {}) {
    const { onKeyDown: originalOnKeyDown, onCompositionStart: originalOnCompositionStart, onCompositionEnd: originalOnCompositionEnd, } = options;
    const c = useRef(false);
    const timer = useRef(null);
    const timer2 = useRef(null);
    const onCompositionStart = usePersistFn((e) => {
        if (timer.current) {
            clearTimeout(timer.current);
            timer.current = null;
        }
        if (timer2.current) {
            clearTimeout(timer2.current);
            timer2.current = null;
        }
        c.current = true;
        originalOnCompositionStart?.(e);
    });
    const onCompositionEnd = usePersistFn((e) => {
        // 使用两层 setTimeout 来处理 Safari 浏览器中 compositionEnd 先于 onKeyDown 触发的问题
        timer.current = setTimeout(() => {
            timer2.current = setTimeout(() => {
                c.current = false;
            });
        });
        originalOnCompositionEnd?.(e);
    });
    const onKeyDown = usePersistFn((e) => {
        // 在 composition 状态下，阻止 ESC 和 Enter（非 shift+Enter）事件的冒泡
        if (c.current &&
            (e.key === "Escape" || (e.key === "Enter" && !e.shiftKey))) {
            e.stopPropagation();
            return;
        }
        originalOnKeyDown?.(e);
    });
    const isComposing = usePersistFn(() => {
        return c.current;
    });
    return {
        onCompositionStart,
        onCompositionEnd,
        onKeyDown,
        isComposing,
    };
}
