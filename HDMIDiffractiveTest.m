function HDMIDiffractiveTest()
%This function will loop through a series of images and load them to the
%SLM so that we can collect measurements of diffracted light and generate a LUT

% Load Blink_C_wrapper.dll
if ~libisloaded('Blink_C_wrapper')
    loadlibrary('Blink_C_wrapper.dll', 'Blink_C_wrapper.h');
end

% This loads the image generation functions
if ~libisloaded('ImageGen')
    loadlibrary('ImageGen.dll', 'ImageGen.h');
end

% call the constructor
calllib('Blink_C_wrapper', 'Create_SDK');
disp('Blink SDK was successfully constructed');

% read the SLM height and width. 
width = calllib('Blink_C_wrapper', 'Get_Width');
height = calllib('Blink_C_wrapper', 'Get_Height');
depth = calllib('Blink_C_wrapper', 'Get_Depth');
bytesPerPixel = 4; % RGBA

% The number of data points we will use in the calibration is 256 (8 bit's)
NumDataPoints = 256;

% If you are generating a global calibration (recommended) the number of regions is 1, 
% if you are generating a regional calibration (typically not necessary) the number of regions is 64
NumRegions = 1;

%allocate an array for our image, and set the wavefront correction to 0 for the LUT calibration process
Image = libpointer('uint8Ptr', zeros(width*height*bytesPerPixel,1));
WFC = libpointer('uint8Ptr', zeros(width*height*bytesPerPixel,1));

% Create an array to hold measurements from the analog input (AI) board. 
% We ususally use a NI USB 6008 or equivalent analog input board.
AI_Intensities = zeros(NumDataPoints,2);

% When generating a calibration you want to use a linear LUT. If you are checking a calibration
% use your custom LUT 
if(height == 1152)
	lut_file = 'C:\Program Files\Meadowlark Optics\Blink 1920 HDMI\LUT Files\1920x1152_linearVoltage.lut';
else
	if(depth == 8)
		lut_file = 'C:\Program Files\Meadowlark Optics\Blink 1920 HDMI\LUT Files\19x12_8bit_linearVoltage.lut';
	end 
	if(depth == 10)
		lut_file = 'C:\Program Files\Meadowlark Optics\Blink 1920 HDMI\LUT Files\19x12_10bit_linearVoltage.lut';
	end
end

% Load the lookup table to the controller.  
calllib('Blink_C_wrapper', 'Load_lut', lut_file);
 
% Start with a blank pattern, and indicate that our images are RGB images
isEightBit = false;
RGB = true;
vertical = true;
if (height == 1152)
	PixelValueOne = 0;
else
	PixelValueOne = 255;
end 
calllib('ImageGen', 'Generate_Solid', Image, WFC, width, height, depth, PixelValueOne, RGB);
calllib('Blink_C_wrapper', 'Write_image', Image, isEightBit);

PixelsPerStripe = 8;
%loop through each region
for Region = 0:(NumRegions-1)

    AI_Index = 1;
	%loop through each graylevel
	for Gray = 0:(NumDataPoints-1)
	
		if (height == 1152)
			PixelValueTwo = Gray;
		else
			PixelValueTwo = 255 - Gray;
		end 	
        %Generate the stripe pattern and mask out current region
        calllib('ImageGen', 'Generate_Stripe', Image, WFC, width, height, depth, PixelValueOne, PixelValueTwo, PixelsPerStripe, vertical, RGB);
        calllib('ImageGen', 'Mask_Image', Image, width, height, depth, Region, NumRegions, RGB);
            
        %write the image
        calllib('Blink_C_wrapper', 'Write_image', Image, isEightBit);
          
        %let the SLM settle for 40 ms (HDMI card can't load images faster than every 33 ms)
        pause(0.04);
            
        %YOU FILL IN HERE...FIRST: read from your specific AI board, note it might help to clean up noise to average several readings
        %SECOND: store the measurement in your AI_Intensities array
        AI_Intensities(AI_Index, 1) = Gray; %This is the difference between the reference and variable graysclae for the datapoint
        AI_Intensities(AI_Index, 2) = 0; % HERE YOU NEED TO REPLACE 0 with YOUR MEASURED VALUE FROM YOUR ANALOG INPUT BOARD

        AI_Index = AI_Index + 1;
	end
        
	% dump the AI measurements to a csv file
	filename = ['Raw' num2str(Region) '.csv'];
	csvwrite(filename, AI_Intensities);  
end

   
%blank the SLM again at the end of the test.
calllib('Blink_C_wrapper', 'Delete_SDK');

if libisloaded('ImageGen')
    unloadlibrary('ImageGen');
end

if libisloaded('Blink_C_wrapper')
    unloadlibrary('Blink_C_wrapper');
end
