/* ══════════════════════════════════════════
   OnyxLab Research Portal — Interactive Effects
   Entrance animations handled by CSS keyframes
   ══════════════════════════════════════════ */

(function () {
    if (typeof gsap === 'undefined') return;

    // Interactive card tilt on mouse move
    document.querySelectorAll('.feature-card').forEach(function (card) {
        card.addEventListener('mousemove', function (e) {
            var rect = card.getBoundingClientRect();
            var x = (e.clientX - rect.left) / rect.width - 0.5;
            var y = (e.clientY - rect.top) / rect.height - 0.5;

            gsap.to(card, {
                rotateY: x * 6,
                rotateX: -y * 6,
                duration: 0.4,
                ease: 'power2.out',
                transformPerspective: 800
            });
        });

        card.addEventListener('mouseleave', function () {
            gsap.to(card, {
                rotateY: 0,
                rotateX: 0,
                duration: 0.5,
                ease: 'power2.out'
            });
        });
    });
})();
