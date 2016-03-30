module.exports = function(grunt) {
  grunt.initConfig({
    concat: {
      js: {
        src: 'static/js/*.js',
        dest: 'static/public/concat.js'
      },
      css: {
        src: 'static/css/*.css',
        dest: 'static/public/concat.css'
      }
    },
    min: {
      js: {
        src: 'static/public/concat.js',
        dest: 'static/public/concat.min.js'
      }
    },
    cssmin: {
      add_banner: {
        options: {
          banner: '/* API Checker Minified CSS was built on <%= grunt.template.today("dd-mm-yyyy") %> using Grunt Task Runner */'
      },
      files: {
        'static/css/main.min.css': ['static/css/main.css'],
        'static/css/custom.min.css': ['static/css/custom.css'],
        'static/css/flat-ui.min.css': ['static/css/flat-ui.css'],
        'static/css/bootstrap.min.css': ['static/css/bootstrap.css']
      }
      }
    },
    cssminall: {
      add_banner: {
        options: {
          banner: '/* Concatinated CSS was built on <%= grunt.template.today("dd-mm-yyyy") %> using Grunt Task Runner */'
      },
      files: {
      'static/public/concat.css': ['static/public/concat.min.css']
      }
      }
    },
    uncss: {
        dist: {
        files: {
            'static/css/main.css': ['index.html','base.html']
        }
        }
    },
    watch: {
      scripts: {
        files: ['static/css/*.css'],
        tasks:['cssmin'],
        options: {
          spawn: false,
        },
      },
    },
  });
  // Load libs
  grunt.loadNpmTasks('grunt-uncss');
  grunt.loadNpmTasks('grunt-contrib-cssmin');
  grunt.loadNpmTasks('grunt-contrib-concat');
  grunt.loadNpmTasks('grunt-contrib-uglify');
  grunt.loadNpmTasks('grunt-contrib-watch');

  grunt.registerTask('default', 'concat min cssmin');
};
