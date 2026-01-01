import React, { useRef, useEffect } from 'react';

const IntroVideo = ({ onComplete }) => {
    const videoRef = useRef(null);
    const videoSrc = "/mis-energy/mis-energy-animation.mp4"; // Absolute path to public asset

    useEffect(() => {
        if (videoRef.current) {
            videoRef.current.play().catch(error => {
                console.warn("Autoplay prevented:", error);
                // Fallback: if autoplay fails, complete immediately
                onComplete();
            });
        }
    }, [onComplete]);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-white">
            <video
                ref={videoRef}
                className="w-full max-w-4xl h-auto object-contain"
                src={videoSrc}
                muted
                playsInline
                onEnded={onComplete}
                style={{ maxHeight: '80vh' }}
            >
                Your browser does not support the video tag.
            </video>
        </div>
    );
};

export default IntroVideo;
