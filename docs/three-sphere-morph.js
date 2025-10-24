/**
 * OnyxLab Morphing Sphere - Sphere ↔ Diamond Logo
 * Click: Sphere morphs into OnyxLab diamond logo
 * Mouse leave: Returns to sphere
 */

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.161.0/build/three.module.js';

class MorphingSphere {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error('Sphere container not found');
            return;
        }

        // State
        this.isMorphed = false;
        this.morphProgress = 0;
        this.targetMorphProgress = 0;
        this.particles = [];
        this.connections = [];

        // Mouse interaction state
        this.mouse = new THREE.Vector2();
        this.targetRotation = new THREE.Vector2();
        this.currentRotation = new THREE.Vector2();

        // Hover state
        this.isHovered = false;
        this.targetScale = 1;
        this.currentScale = 1;

        // Configuration
        this.config = {
            particleCount: 60,
            sphereRadius: 150,
            logoSize: 180,
            morphSpeed: 0.05,
            colors: {
                blue: 0x0a84ff,
                purple: 0x8b7ba8,
                teal: 0x5a9aa8,
                // Diamond pearl gradient colors
                diamondDark: 0x4a0e4e,   // Deep dark purple
                diamondLight: 0x9b59b6,  // Lighter purple pearl
                diamondHighlight: 0xd4a5d4 // Pearl shimmer
            }
        };

        this.init();
        this.animate();
        this.setupEventListeners();
    }

    init() {
        // Scene
        this.scene = new THREE.Scene();

        // Camera
        const aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 2000);
        this.camera.position.z = 400;

        // Renderer
        this.renderer = new THREE.WebGLRenderer({
            alpha: true,
            antialias: true
        });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.container.appendChild(this.renderer.domElement);

        // Group
        this.group = new THREE.Group();
        this.scene.add(this.group);

        // Create particles with sphere and logo positions
        this.createParticles();
        this.createConnections();
        this.createCoreGlow();

        console.log('MorphingSphere: Initialized successfully');
    }

    createParticles() {
        const geometry = new THREE.SphereGeometry(2.5, 12, 12);

        for (let i = 0; i < this.config.particleCount; i++) {
            // Sphere position (Fibonacci distribution)
            const phi = Math.acos(1 - 2 * (i + 0.5) / this.config.particleCount);
            const theta = Math.PI * (1 + Math.sqrt(5)) * i;

            const sphereX = Math.cos(theta) * Math.sin(phi) * this.config.sphereRadius;
            const sphereY = Math.sin(theta) * Math.sin(phi) * this.config.sphereRadius;
            const sphereZ = Math.cos(phi) * this.config.sphereRadius;

            // Logo position (diamond shape)
            const logoPos = this.getDiamondPosition(i, this.config.particleCount);

            // Color based on depth
            const depthFactor = (sphereZ + this.config.sphereRadius) / (this.config.sphereRadius * 2);
            const color = new THREE.Color(this.config.colors.blue).lerp(
                new THREE.Color(this.config.colors.purple),
                depthFactor
            );

            const material = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.85
            });

            const particle = new THREE.Mesh(geometry, material);
            particle.position.set(sphereX, sphereY, sphereZ);

            // Store both positions
            particle.userData = {
                spherePos: new THREE.Vector3(sphereX, sphereY, sphereZ),
                logoPos: new THREE.Vector3(logoPos.x, logoPos.y, logoPos.z),
                originalColor: color.clone()
            };

            this.particles.push(particle);
            this.group.add(particle);
        }
    }

    getDiamondPosition(index, total) {
        // OnyxLab diamond: Flat table top, pronounced facets, dramatic taper to point
        const size = this.config.logoSize;
        const layers = 5; // Reduced from 6 to 5 layers
        const particlesPerLayer = Math.floor(total / layers);

        const layer = Math.floor(index / particlesPerLayer);
        const indexInLayer = index % particlesPerLayer;

        let x, y, z;
        const angle = (indexInLayer / particlesPerLayer) * Math.PI * 2;
        
        // Add facet angle offset for more geometric appearance
        const facetOffset = Math.PI / 8; // 22.5 degrees for octagonal facets
        const facetAngle = angle + facetOffset;

        switch(layer) {
            case 0: // Table (flat top) - Wider flat surface
                y = size * 0.35;
                if (indexInLayer === 0) {
                    // Center point
                    x = 0;
                    z = 0;
                } else {
                    // Octagonal ring - wider for prominence
                    const octAngle = ((indexInLayer - 1) / 8) * Math.PI * 2;
                    const topRadius = size * 0.5;
                    x = Math.cos(octAngle) * topRadius;
                    z = Math.sin(octAngle) * topRadius;
                }
                break;

            case 1: // Girdle (widest point) - Maximum width
                y = 0;
                const girdleRadius = size * 0.95;
                x = Math.cos(angle) * girdleRadius;
                z = Math.sin(angle) * girdleRadius;
                break;

            case 2: // Upper pavilion (dramatic taper begins)
                y = -size * 0.35;
                const upperPavilionRadius = size * 0.65;
                x = Math.cos(facetAngle) * upperPavilionRadius;
                z = Math.sin(facetAngle) * upperPavilionRadius;
                break;

            case 3: // Lower pavilion (steep angle to point)
                y = -size * 0.7;
                const lowerPavilionRadius = size * 0.25;
                x = Math.cos(angle) * lowerPavilionRadius;
                z = Math.sin(angle) * lowerPavilionRadius;
                break;

            default: // Culet (sharp bottom point)
                y = -size * 1.1;
                if (indexInLayer === 0) {
                    x = 0;
                    z = 0;
                } else {
                    // Tiny ring at very bottom for definition
                    const culetRadius = size * 0.02;
                    x = Math.cos(angle) * culetRadius;
                    z = Math.sin(angle) * culetRadius;
                }
                break;
        }

        return { x, y, z };
    }

    createConnections() {
        const material = new THREE.LineBasicMaterial({
            color: this.config.colors.teal,
            transparent: true,
            opacity: 0.15,
            blending: THREE.AdditiveBlending
        });

        // Create connections between nearby particles
        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const distance = this.particles[i].position.distanceTo(
                    this.particles[j].position
                );

                if (distance < 120) {
                    const geometry = new THREE.BufferGeometry().setFromPoints([
                        this.particles[i].position,
                        this.particles[j].position
                    ]);

                    const line = new THREE.Line(geometry, material);
                    line.userData = {
                        particleA: i,
                        particleB: j
                    };

                    this.connections.push(line);
                    this.group.add(line);
                }
            }
        }
    }

    createCoreGlow() {
        const geometry = new THREE.SphereGeometry(35, 24, 24);
        const material = new THREE.MeshBasicMaterial({
            color: this.config.colors.blue,
            transparent: true,
            opacity: 0.12,
            blending: THREE.AdditiveBlending
        });
        this.core = new THREE.Mesh(geometry, material);
        this.group.add(this.core);

        // Outer glow
        for (let i = 1; i <= 2; i++) {
            const glowGeometry = new THREE.SphereGeometry(35 + i * 15, 24, 24);
            const glowMaterial = new THREE.MeshBasicMaterial({
                color: this.config.colors.blue,
                transparent: true,
                opacity: 0.04 / i,
                blending: THREE.AdditiveBlending,
                side: THREE.BackSide
            });
            const glow = new THREE.Mesh(glowGeometry, glowMaterial);
            this.group.add(glow);
        }
    }

    setupEventListeners() {
        // Mouse move for parallax rotation
        this.container.addEventListener('mousemove', (e) => this.handleMouseMove(e));

        // Hover effects
        this.container.addEventListener('mouseenter', () => {
            this.isHovered = true;
            this.targetScale = 1.15;
        });

        this.container.addEventListener('mouseleave', () => {
            this.isHovered = false;
            this.targetScale = 1;

            // Return to sphere when mouse leaves
            if (this.isMorphed) {
                this.isMorphed = false;
                this.targetMorphProgress = 0;
            }
        });

        // Click to toggle morph
        this.container.addEventListener('click', () => {
            this.isMorphed = !this.isMorphed;
            this.targetMorphProgress = this.isMorphed ? 1 : 0;
        });

        // Resize
        window.addEventListener('resize', () => this.onResize());

        // Visibility API
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.renderer.setAnimationLoop(null);
            } else {
                this.animate();
            }
        });
    }

    onResize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;

        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    handleMouseMove(event) {
        const rect = this.container.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        // Smooth mouse influence
        this.targetRotation.x = this.mouse.y * 0.3;
        this.targetRotation.y = this.mouse.x * 0.3;
    }

    updateRotation() {
        // Smooth interpolation towards target rotation
        this.currentRotation.x += (this.targetRotation.x - this.currentRotation.x) * 0.05;
        this.currentRotation.y += (this.targetRotation.y - this.currentRotation.y) * 0.05;

        // Apply mouse-based rotation
        this.group.rotation.x = this.currentRotation.x;
        this.group.rotation.y += this.currentRotation.y * 0.01;

        // Auto-rotate
        this.group.rotation.y += 0.002;
    }

    updateScale() {
        // Smooth scale transition
        this.currentScale += (this.targetScale - this.currentScale) * 0.1;
        this.group.scale.set(this.currentScale, this.currentScale, this.currentScale);
    }

    updateMorph() {
        // Smooth morph progress
        this.morphProgress += (this.targetMorphProgress - this.morphProgress) * this.config.morphSpeed;

        // Update particle positions and colors
        this.particles.forEach((particle, i) => {
            const { spherePos, logoPos, originalColor } = particle.userData;

            // Interpolate between sphere and logo positions
            particle.position.lerpVectors(spherePos, logoPos, this.morphProgress);

            // Diamond pearl gradient color transition
            if (this.morphProgress > 0.01) {
                // Calculate depth-based gradient for diamond (y-position based)
                const yPos = particle.position.y;
                const normalizedY = (yPos + this.config.logoSize) / (this.config.logoSize * 1.5);
                
                // Create pearl gradient: dark purple at top, lighter at middle, shimmer at bottom
                const darkPurple = new THREE.Color(this.config.colors.diamondDark);
                const lightPurple = new THREE.Color(this.config.colors.diamondLight);
                const pearlShimmer = new THREE.Color(this.config.colors.diamondHighlight);
                
                let diamondColor;
                if (normalizedY > 0.6) {
                    // Top half: dark to light purple
                    diamondColor = darkPurple.clone().lerp(lightPurple, (normalizedY - 0.6) * 2.5);
                } else {
                    // Bottom half: light purple to pearl shimmer
                    diamondColor = lightPurple.clone().lerp(pearlShimmer, (0.6 - normalizedY) * 1.7);
                }
                
                // Interpolate between original sphere color and diamond color
                particle.material.color.lerpColors(originalColor, diamondColor, this.morphProgress);
            } else {
                // Return to original sphere color
                particle.material.color.copy(originalColor);
            }
        });

        // Update connections
        this.connections.forEach(line => {
            const { particleA, particleB } = line.userData;
            const positions = line.geometry.attributes.position;

            positions.setXYZ(0,
                this.particles[particleA].position.x,
                this.particles[particleA].position.y,
                this.particles[particleA].position.z
            );
            positions.setXYZ(1,
                this.particles[particleB].position.x,
                this.particles[particleB].position.y,
                this.particles[particleB].position.z
            );

            positions.needsUpdate = true;
        });
    }

    animate() {
        this.renderer.setAnimationLoop(() => {
            // Update morph animation
            this.updateMorph();

            // Update mouse-based rotation and auto-rotation
            this.updateRotation();

            // Update hover scale effect
            this.updateScale();

            // Pulse core glow
            if (this.core) {
                const pulse = Math.sin(Date.now() * 0.001) * 0.03 + 0.12;
                this.core.material.opacity = pulse;
            }

            // Render
            this.renderer.render(this.scene, this.camera);
        });
    }
}

// Auto-initialize
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        new MorphingSphere('sphere-container');
    });
} else {
    new MorphingSphere('sphere-container');
}
