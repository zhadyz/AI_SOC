/**
 * OnyxLab Research Portal - Interactive Orb with Particle Network
 * Cursor-reactive sphere visualization with network connections
 * Date: October 24, 2025
 */

(function() {
    'use strict';

    class InteractiveOrb {
        constructor(canvas) {
            this.canvas = canvas;
            this.ctx = canvas.getContext('2d', { alpha: true });
            this.particles = [];
            this.mouse = { x: 0, y: 0, active: false };
            this.frame = 0;
            this.animationId = null;

            // Configuration
            this.config = {
                particleCount: 60,
                coreColor: { r: 10, g: 132, b: 255 },      // Blue
                accentColor: { r: 139, g: 123, b: 168 },   // Purple
                networkColor: { r: 90, g: 154, b: 168 },   // Teal
                coreRadius: 120,
                orbitRadius: 180,
                rotationSpeed: 0.0005,
                mouseInfluence: 80,
                connectionDistance: 150
            };

            // Performance flags
            this.prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            this.pixelRatio = Math.min(window.devicePixelRatio || 1, 2);

            this.init();
        }

        init() {
            this.resize();
            this.initParticles();

            window.addEventListener('resize', () => this.resize());
            this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
            this.canvas.addEventListener('mouseleave', () => this.handleMouseLeave());

            if (!this.prefersReducedMotion) {
                this.start();
            }
        }

        initParticles() {
            this.particles = [];
            const centerX = this.canvas.width / (2 * this.pixelRatio);
            const centerY = this.canvas.height / (2 * this.pixelRatio);

            for (let i = 0; i < this.config.particleCount; i++) {
                // Distribute particles on sphere surface using Fibonacci sphere
                const phi = Math.acos(1 - 2 * (i + 0.5) / this.config.particleCount);
                const theta = Math.PI * (1 + Math.sqrt(5)) * i;

                this.particles.push({
                    // 3D coordinates
                    phi: phi,
                    theta: theta,
                    radius: this.config.orbitRadius,

                    // 2D projection
                    x: centerX,
                    y: centerY,
                    z: 0,

                    // Visual properties
                    size: Math.random() * 2 + 1,
                    alpha: Math.random() * 0.5 + 0.5,
                    speedOffset: Math.random() * 0.5 + 0.5,

                    // Original position for mouse interaction
                    originalX: 0,
                    originalY: 0
                });
            }
        }

        resize() {
            const rect = this.canvas.getBoundingClientRect();
            this.canvas.width = rect.width * this.pixelRatio;
            this.canvas.height = rect.height * this.pixelRatio;
            this.canvas.style.width = `${rect.width}px`;
            this.canvas.style.height = `${rect.height}px`;
            this.ctx.scale(this.pixelRatio, this.pixelRatio);
            this.initParticles();
        }

        handleMouseMove(e) {
            const rect = this.canvas.getBoundingClientRect();
            this.mouse.x = e.clientX - rect.left;
            this.mouse.y = e.clientY - rect.top;
            this.mouse.active = true;
        }

        handleMouseLeave() {
            this.mouse.active = false;
        }

        start() {
            if (!this.animationId) {
                this.animate();
            }
        }

        stop() {
            if (this.animationId) {
                cancelAnimationFrame(this.animationId);
                this.animationId = null;
            }
        }

        animate() {
            this.renderFrame();
            this.frame++;
            this.animationId = requestAnimationFrame(() => this.animate());
        }

        renderFrame() {
            const w = this.canvas.width / this.pixelRatio;
            const h = this.canvas.height / this.pixelRatio;
            const centerX = w / 2;
            const centerY = h / 2;

            // Clear canvas
            this.ctx.clearRect(0, 0, w, h);

            // Update particle positions (3D rotation)
            const time = this.frame * this.config.rotationSpeed;

            this.particles.forEach((p) => {
                // Rotate around Y and X axis
                const rotY = time * p.speedOffset;
                const rotX = time * p.speedOffset * 0.7;

                // Convert spherical to 3D Cartesian
                const x3d = p.radius * Math.sin(p.phi + rotY) * Math.cos(p.theta + rotX);
                const y3d = p.radius * Math.sin(p.phi + rotY) * Math.sin(p.theta + rotX);
                const z3d = p.radius * Math.cos(p.phi + rotY);

                // Simple perspective projection
                const perspective = 300;
                const scale = perspective / (perspective + z3d);

                p.x = centerX + x3d * scale;
                p.y = centerY + y3d * scale;
                p.z = z3d;

                // Store original position for mouse interaction
                p.originalX = p.x;
                p.originalY = p.y;

                // Mouse influence
                if (this.mouse.active) {
                    const dx = this.mouse.x - p.x;
                    const dy = this.mouse.y - p.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);

                    if (distance < this.config.mouseInfluence) {
                        const force = (this.config.mouseInfluence - distance) / this.config.mouseInfluence;
                        p.x -= dx * force * 0.3;
                        p.y -= dy * force * 0.3;
                    }
                }
            });

            // Sort particles by z-index for proper layering
            const sortedParticles = [...this.particles].sort((a, b) => a.z - b.z);

            // Draw connections (network lines)
            this.ctx.globalCompositeOperation = 'lighter';
            sortedParticles.forEach((p, i) => {
                sortedParticles.slice(i + 1).forEach((p2) => {
                    const dx = p.x - p2.x;
                    const dy = p.y - p2.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);

                    if (distance < this.config.connectionDistance) {
                        const opacity = (1 - distance / this.config.connectionDistance) * 0.3;
                        const c = this.config.networkColor;

                        this.ctx.beginPath();
                        this.ctx.strokeStyle = `rgba(${c.r}, ${c.g}, ${c.b}, ${opacity})`;
                        this.ctx.lineWidth = 0.5;
                        this.ctx.moveTo(p.x, p.y);
                        this.ctx.lineTo(p2.x, p2.y);
                        this.ctx.stroke();
                    }
                });
            });

            // Draw central glow
            const coreGradient = this.ctx.createRadialGradient(
                centerX, centerY, 0,
                centerX, centerY, this.config.coreRadius
            );
            const core = this.config.coreColor;
            coreGradient.addColorStop(0, `rgba(${core.r}, ${core.g}, ${core.b}, 0.4)`);
            coreGradient.addColorStop(0.5, `rgba(${core.r}, ${core.g}, ${core.b}, 0.2)`);
            coreGradient.addColorStop(1, `rgba(${core.r}, ${core.g}, ${core.b}, 0)`);

            this.ctx.fillStyle = coreGradient;
            this.ctx.fillRect(0, 0, w, h);

            // Draw particles
            this.ctx.globalCompositeOperation = 'lighter';
            sortedParticles.forEach((p) => {
                // Depth-based coloring (closer = blue, farther = purple)
                const depthFactor = (p.z + this.config.orbitRadius) / (this.config.orbitRadius * 2);
                const color = this.interpolateColor(
                    this.config.coreColor,
                    this.config.accentColor,
                    depthFactor
                );

                const gradient = this.ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 3);
                gradient.addColorStop(0, `rgba(${color.r}, ${color.g}, ${color.b}, ${p.alpha})`);
                gradient.addColorStop(1, `rgba(${color.r}, ${color.g}, ${color.b}, 0)`);

                this.ctx.fillStyle = gradient;
                this.ctx.beginPath();
                this.ctx.arc(p.x, p.y, p.size * 3, 0, Math.PI * 2);
                this.ctx.fill();
            });

            this.ctx.globalCompositeOperation = 'source-over';
        }

        interpolateColor(c1, c2, factor) {
            return {
                r: Math.round(c1.r + (c2.r - c1.r) * factor),
                g: Math.round(c1.g + (c2.g - c1.g) * factor),
                b: Math.round(c1.b + (c2.b - c1.b) * factor)
            };
        }

        destroy() {
            this.stop();
            window.removeEventListener('resize', () => this.resize());
        }
    }

    // Auto-initialize
    function initInteractiveOrb() {
        const canvas = document.getElementById('hero-gradient-canvas');
        if (!canvas) {
            console.warn('[InteractiveOrb] Canvas element not found');
            return null;
        }

        const orb = new InteractiveOrb(canvas);
        console.log('[InteractiveOrb] Initialized successfully');
        return orb;
    }

    // Export
    window.InteractiveOrb = InteractiveOrb;
    window.initInteractiveOrb = initInteractiveOrb;

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initInteractiveOrb);
    } else {
        initInteractiveOrb();
    }

})();
