// Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
var gulp = require('gulp');
var gutil = require('gulp-util');
var browserify = require('browserify');
var source = require('vinyl-source-stream');
var watchify = require('watchify');
var shell = require('gulp-shell');
var uglify = require('gulp-uglify');
var babelify = require("babelify");
var envify = require('envify/custom');
var buffer = require('gulp-buffer');
var rev = require("gulp-rev");
var revReplace = require("gulp-rev-replace");

var buildConfig = require("./build.config.js");


function makeBuild(development) {
    process.env.NODE_ENV = 'production';
    if(development) {
        process.env.NODE_ENV = 'development';
    }

    var makeBrowserify = function() {
        var bundle = browserify("main.js", {
            basedir: __dirname + "/web/js",
            paths: __dirname + "/web/js",
            extensions: [".jsx", ".js"],
            cache: {},
            debug: development,
            packageCache: {}
        });
        if(development) {
            bundle.plugin(watchify);
        }
        bundle.transform(babelify.configure({
            "presets": ["react", "es2015"]
        }));
        bundle.transform(envify({
            NODE_ENV: development ? "development" : "production",
            HIDE_HOSTNAME_SUFFIXES: buildConfig.hideHostnameSuffixes,
            REFERENCE_MAIL: buildConfig.referenceMail,
            AUTH_PAGE: buildConfig.authPage,
            SESSIONID_COOKIE: buildConfig.sessionidCookie
        }));
        return bundle;
    };

    var b = makeBrowserify();
    if(development) {
        b.on('update', bundle);
    }

    function bundle() {
        var stream = b.bundle()
            .pipe(source('bundle.js'))
            .pipe(buffer());
        if(!development) {
            stream = stream.pipe(uglify())
            .pipe(rev())
            .pipe(revReplace())
            .pipe(gulp.dest('./web/static/js'))
            .pipe(rev.manifest());
        }
        return stream.pipe(gulp.dest('./web/static/js')).on('error', gutil.log);
    }
    return bundle();
}

gulp.task('assets', function() {
    return makeBuild(false);
});

gulp.task('build', ['assets'], function() {
    var manifest = gulp.src("./web/static/js/rev-manifest.json");

    return gulp.src("./web/index.html")
        .pipe(revReplace({manifest: manifest}))
        .pipe(gulp.dest("./web/static/html/"));
});

gulp.task('dev', ['devAssets'], function() {
    return gulp.src("./web/index.html")
        .pipe(gulp.dest("./web/static/html/"));
});

gulp.task('devAssets', function() {
    return makeBuild(true);
});

gulp.task('test', shell.task([
    'npm test'
]));

gulp.task('default', ['build']);
