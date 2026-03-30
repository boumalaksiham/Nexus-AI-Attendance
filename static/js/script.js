// script.js

// 📘 Purpose:
// This JavaScript file uses the GSAP (GreenSock Animation Platform) library to 
// animate different sections of the homepage as they load or scroll into view.

// 🚀 Trigger all animations only after the DOM is fully loaded
document.addEventListener("DOMContentLoaded", () => {

    // ========================
    // 🎯 Hero Section Animation
    // ========================
    // Animate the main heading by sliding it in from the top
    gsap.from(".hero h2", {
        duration: 1,
        y: -50,           // Move upward 50px
        opacity: 0        // Start invisible
    });

    // Animate the paragraph below the heading by sliding it in from the bottom with a delay
    gsap.from(".hero p", {
        duration: 1,
        y: 50,            // Move downward 50px
        opacity: 0,
        delay: 0.5        // Starts after heading finishes
    });

    // ==========================
    // 🧭 Split Section Animation
    // ==========================
    // Animate each ".split-item" inside the ".split" section when scrolled into view
    gsap.from(".split-item", {
        scrollTrigger: ".split",  // Requires ScrollTrigger plugin
        duration: 1,
        opacity: 0,
        y: 50,
        stagger: 0.3              // Animates each item one after another
    });

    // =============================
    // ✨ Features Section Animation
    // =============================
    // Animate each ".feature" inside the ".features" section when it scrolls into view
    gsap.from(".features .feature", {
        scrollTrigger: ".features",
        duration: 1,
        opacity: 0,
        y: 100,
        stagger: 0.2
    });

    // =====================================
    // 🔄 Interactive Section (Custom Area)
    // =====================================
    // Animate a special section (e.g., animated graph or card) from the left
    gsap.from("#animated-section", {
        scrollTrigger: "#animated-section",
        duration: 1,
        x: -100,
        opacity: 0
    });

    // ==============================
    // 📢 Call-to-Action (CTA) Section
    // ==============================
    // Slide in the CTA heading from the top
    gsap.from(".cta h2", {
        scrollTrigger: ".cta",
        duration: 1,
        y: -50,
        opacity: 0
    });

    // Slide in the CTA button from the bottom with a slight delay
    gsap.from(".cta button", {
        scrollTrigger: ".cta",
        duration: 1,
        y: 50,
        opacity: 0,
        delay: 0.5
    });

});
