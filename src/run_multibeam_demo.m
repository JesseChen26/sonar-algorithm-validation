% Multibeam sonar algorithm demo
% This MATLAB script mirrors the Python workflow at a readable level.
% It loads CSV/NPZ-derived results if available and demonstrates the
% delay-and-sum beamforming equations used in the project.

clear; clc; close all;

root = fileparts(fileparts(mfilename('fullpath')));
metricsPath = fullfile(root, 'results', 'cfar_detection_metrics.csv');

if exist(metricsPath, 'file')
    T = readtable(metricsPath);
    disp(T);
else
    warning('Run enhance_sonar_job_project.py first to create CFAR metrics.');
end

% Algorithm sketch for MATLAB implementation:
% raw(ping, element, range) is complex baseband echo.
% element_x is the array coordinate in meters.
% ranges is the range vector in meters.
% lambda = c / fc.
%
% for each beam angle theta:
%   w = exp(1j * 2*pi * element_x * sin(theta) / lambda);
%   y(theta, range) = sum_element mean_ping(raw) .* w
%   image(theta, range) = 20*log10(abs(y) / max(abs(y)))
%
% Python produces the validated reference figures:
%   results/02_delay_sum_range_angle_map.png
%   results/05_cfar_detection_overlay.png
%   results/06_cfar_threshold_map.png

figure('Name', 'Project result preview');
img = imread(fullfile(root, 'results', '05_cfar_detection_overlay.png'));
imshow(img);
title('2D CFAR detection overlay on beamformed range-angle map');
