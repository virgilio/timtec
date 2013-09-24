(function (angular) {
    "use strict";

    var app = angular.module('answer', ['ngRoute', 'ngResource', "ngCookies"]);

    // Uses the csrftoken from the cookie
    app.run(function ($http, $cookies) {
        $http.defaults.headers.common['X-CSRFToken'] = $cookies['csrftoken'];
    });
    // Avoid jumping to top after click in anchor '#'
    app.value('$anchorScroll', angular.noop);

    app.config(['$routeProvider', function ($routeProvider) {
        console.log('ngRoute!!!');
        $routeProvider
            .when('/forum/question/answer/create', {
                templateUrl: 'answer_create.html',
                controller: 'AnswerCtrl'});
    }]);

    app.controller('AnswerCtrl', ['$scope', 'Answer',
        function ($scope, Answer) {
            var questionId = 1;
            var answer_text = 'Angular Angular Angular AngularAngular AngularAngularAngularAngularAngularAngular Angular Angular Angular Angular Angular';
            $scope.new_answer = Answer.create({question: questionId, text: answer_text});
    }]);

    app.factory('Answer', function($resource){
        return $resource('/api/answer/', {}, {
            create: {method: 'POST'}
        });
    });

})(angular);

$(document).ready(function() {
    $('.comment-form').hide();
    $('.add-comment-link').click(function(e) {
        e.preventDefault();
        $(this).parent().parent().height(170);
        $(this).parent().parent().find('form').slideDown();
        $(this).hide();
    });

    $('.cancel-comment').click(function(e) {
        e.preventDefault();
        $(this).parent().parent().slideUp();
        $(this).parent().parent().parent().find('.add-comment-link').slideDown().show();
        $(this).parent().parent().parent().height(30);
    });
    $('nav.course-sections > a > span').tooltip();
});