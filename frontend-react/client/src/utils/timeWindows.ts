export type TimeWindowGranularity = 'shift' | 'day' | 'week' | 'month';

export interface TimeWindow {
    from: Date;
    to: Date;
    granularity: TimeWindowGranularity;
}

export const getTimeWindow = (granularity: TimeWindowGranularity): TimeWindow => {
    // We construct dates relative to SP time
    // Note: This is a simplification. Ideally we'd use a library like luxon or date-fns-tz
    // But for now we'll use native Date with offset manipulation if needed, 
    // or just rely on the backend for critical calcs and here just for display/request params.
    // The backend ignores the frontend's specific timestamps for 'shift'/'day' etc 
    // and calculates them itself based on the 'granularity' param.
    // So here we mostly need to return the granularity string.

    // However, if we need to display the range in the UI:
    const now = new Date(); // Local browser time
    let from = new Date(now);
    let to = new Date(now);

    // We will let the backend handle the exact TZ math for the API.
    // This function is mainly used for UI placeholders if needed.

    return { from, to, granularity };
};

export const formatTimeWindow = (window: TimeWindow): string => {
    // If window comes from API (which has from/to strings), use them
    // Otherwise format local dates
    return `${window.granularity.toUpperCase()}`;
};
