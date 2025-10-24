/**
 * Hero Section Animated Gradient
 * Smooth animated gradient mesh for "Research-Grade AI for Real-World Impact"
 */

(function() {
    const canvas = document.getElementById('hero-gradient-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let animationId;

    // Resize canvas to fill hero section
    function resizeCanvas() {
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
    }

    // Gradient animation state
    let time = 0;

    function drawGradient() {
        const width = canvas.width;
        const height = canvas.height;

        // Create animated gradient
        const gradient = ctx.createLinearGradient(
            0,
            0,
            width,
            height
        );

        // Animated color stops - subtle purple/blue theme
        const offset1 = 0.3 + Math.sin(time * 0.5) * 0.1;
        const offset2 = 0.7 + Math.cos(time * 0.3) * 0.1;

        gradient.addColorStop(0, `rgba(10, 132, 255, ${0.15 + Math.sin(time) * 0.05})`); // Blue
        gradient.addColorStop(offset1, `rgba(139, 123, 168, ${0.12 + Math.cos(time * 0.7) * 0.03})`); // Purple
        gradient.addColorStop(offset2, `rgba(90, 154, 168, ${0.1 + Math.sin(time * 1.2) * 0.03})`); // Teal
        gradient.addColorStop(1, `rgba(155, 89, 182, ${0.08 + Math.cos(time * 0.9) * 0.02})`); // Deep purple

        // Clear and fill
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, width, height);

        // Add radial glow overlay at center
        const radialGradient = ctx.createRadialGradient(
            width * 0.5,
            height * 0.4,
            0,
            width * 0.5,
            height * 0.4,
            width * 0.6
        );

        radialGradient.addColorStop(0, `rgba(10, 132, 255, ${0.2 + Math.sin(time * 0.8) * 0.05})`);
        radialGradient.addColorStop(0.5, 'rgba(10, 132, 255, 0.05)');
        radialGradient.addColorStop(1, 'rgba(10, 132, 255, 0)');

        ctx.fillStyle = radialGradient;
        ctx.fillRect(0, 0, width, height);
    }

    function animate() {
        time += 0.01;
        drawGradient();
        animationId = requestAnimationFrame(animate);
    }

    // Initialize
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    animate();

    // Cleanup on visibility change
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            cancelAnimationFrame(animationId);
        } else {
            animate();
        }
    });

    console.log('[Hero Gradient] Initialized');
})();
