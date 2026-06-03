window.HELP_IMPROVE_VIDEOJS = false;

$(document).ready(function() {
    // Toggle the mobile navbar burger menu.
    $(".navbar-burger").click(function() {
      $(".navbar-burger").toggleClass("is-active");
      $(".navbar-menu").toggleClass("is-active");
    });

    // FPS-Bench example carousel: one wide filmstrip per slide.
    var options = {
      slidesToScroll: 1,
      slidesToShow: 1,
      loop: true,
      infinite: true,
      autoplay: true,
      autoplaySpeed: 5000,
      pagination: true,
      navigation: true,
    };

    bulmaCarousel.attach('.carousel', options);

    bulmaSlider.attach();
});
