import React, { useRef, useEffect } from 'react';

interface SplashScreenProps {
    onComplete: () => void;
}

const SplashScreen: React.FC<SplashScreenProps> = ({ onComplete }) => {
    const videoRef = useRef<HTMLVideoElement>(null);

    useEffect(() => {
        if (videoRef.current) {
            // Autoplay MUTED (Garantido pela maioria dos browsers)
            videoRef.current.play().catch(error => {
                console.warn("Autoplay muted prevented (unlikely):", error);
                // Fallback: se falhar mesmo mudo (raro), avança
                onComplete();
            });
        }
    }, [onComplete]);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-white">
            <video
                ref={videoRef}
                className="w-full max-w-4xl h-auto object-contain"
                src={`${import.meta.env.BASE_URL}intro.mp4`}
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

export default SplashScreen;
