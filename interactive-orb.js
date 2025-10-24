/**
 * Hero Gradient Canvas Animation
 * Subtle animated gradient overlay for hero section
 */

(function() {
    const canvas = document.getElementById('hero-gradient-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let animationId;

    function resize() {
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
    }

    let time = 0;

    function draw() {
        const w = canvas.width;
        const h = canvas.height;

        // Clear canvas
        ctx.clearRect(0, 0, w, h);

        // Animated radial gradient - subtle and slow
        const gradient = ctx.createRadialGradient(
            w * (0.4 + Math.sin(time * 0.3) * 0.1),
            h * (0.3 + Math.cos(time * 0.2) * 0.1),
            0,
            w * 0.5,
            h * 0.5,
            w * 0.8
        );

        gradient.addColorStop(0, 'rgba(10, 132, 255, 0.08)');
        gradient.addColorStop(0.5, 'rgba(139, 123, 168, 0.04)');
        gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');

        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, w, h);

        time += 0.01;
        animationId = requestAnimationFrame(draw);
    }

    resize();
    window.addEventListener('resize', resize);
    draw();

    // Cleanup on visibility change
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            cancelAnimationFrame(animationId);
        } else {
            draw();
        }
    });

    console.log('[Interactive Orb] Initialized');
})();
