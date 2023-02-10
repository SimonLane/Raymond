// This test script uses the main microscope control board to drive the scan mirror to perform a z-stack
// also controls the laser board to turn on/off between z-scans 
// not yet implemented laser (trigger) control between single scans

#include <SPI.h>
#include <i2c_t3.h>
#define MEM_LEN 256
char databuf[MEM_LEN];

const int slaveSelectPin = 10;
const int slaveReadyPin = 35;
const int trigger_pin_SM = 34; //trigger pin for scan mirror
const int trigger_pin_IB = 36; //trigger pin for illumination board
const int trigger_pin_cam = 25; //trigger pin to start camera acquisition
uint8_t data;
uint8_t target = 0x66;        //I2C address for illumination board


void setup() {
  //I2C
  Wire1.begin(I2C_MASTER, 0x00, I2C_PINS_37_38, I2C_PULLUP_EXT, 400000);
  Wire1.setDefaultTimeout(200000);            // 200ms
  memset(databuf, 0, sizeof(databuf));        //incoming I2C data buffer
  
  Serial.begin(115200);
  pinMode (slaveSelectPin, OUTPUT);
  pinMode (2, OUTPUT);
  pinMode (13, OUTPUT);
  pinMode (trigger_pin_cam, OUTPUT); 
  pinMode (slaveReadyPin, INPUT);
  pinMode (trigger_pin_SM, OUTPUT);
  pinMode (trigger_pin_IB, OUTPUT);
  digitalWrite (slaveSelectPin, HIGH);
  SPI.begin(); 
  delay(1000);

//INPUT stage
  sendWriteSPI(0x40005102,0x60,generateSPFPR(1));   //Select signal generator as active input for X and static for Y axis (start at top of FOV (1))
  sendWriteSPI(0x60006100,0x02,0x02);               //Configure both axes signal unit (02: XY units; 01: OF units; 00: current) OF = optical feedback
  sendWriteSPI(0x60026003,0x03,generateSPFPR(0.5)); //Configure signal shape & Hz (04: Pulse; 03: sawtooth; 02: Square; 01: Triangle; 00: sinusolidal)
                                                     // FOV is 0.3 of the full (-1 to 1) scan range, so 1s exposure requires 0.3Hz
  sendWriteSPI(0x60046007,generateSPFPR(1.0),0x01);  //Configure Amplitude and cycles (Single point floating representations)
                                                     //Cycles (int) - 0x8001 = (dec)-1 = infinte
  sendWriteSPI(0x60096109,0x01,0x00);                //external trigger
  sendWriteSPI(0x60016101,0x01,0x01);                //Set run flag, both axes
//CONDITIONING stage  
  sendWriteSPI(0x98009801,generateSPFPR(0.05),generateSPFPR(0.0050));      // X  (Gain, Offset), X uses only +ve side and 
                                                                           // is wider than FOV:    FOV[+0.2 to +0.8]
  sendWriteSPI(0x99009901,generateSPFPR(0.01),generateSPFPR(0.041));     // Y  (Gain, Offset), Y is symetrical and full 
                                                                           // height of FOV:        FOV[-1 to +1]
//CONTROL stage  
  sendWriteSPI(0x40024007,0xC0,0xC0);       //Activate closed loop control for both axes
}

float z = 1.0;

void trigger_scan_mirror(){
  digitalWrite(trigger_pin_SM,1);
  delayMicroseconds(100);
  digitalWrite(trigger_pin_SM,0);
}

void trigger_camera(){
  digitalWrite(trigger_pin_cam,1);
  delayMicroseconds(10);
  digitalWrite(trigger_pin_cam,0);
}

void set_z(int z){
  sendWriteSPI(0x51020000,generateSPFPR(0),0x00); //set z position
}

bool flag1 = false;
bool flag2 = false;
bool flag3 = false;
bool flag4 = false;

long unsigned next_start = millis();

void loop(){
  if(millis() > next_start + 1500){
    next_start = millis();
    Serial.print("0-");
    Serial.println(millis());
    
    flag1 = false;
    flag2 = false;
    flag3 = false;
    flag4 = false;
    }

  if(millis() > next_start + 0){
    
    if (flag1==false){
      trigger_scan_mirror();
      flag1=true;
      Serial.print("1-");
      Serial.println(millis());
    }
  }

  if(millis() > next_start + 0){ 
    
    if (flag2==false){
      digitalWrite(trigger_pin_IB,1);  // laser on
      flag2 = true;
      Serial.print("2-");
      Serial.println(millis());
    }
  }

  if(millis() > next_start + 0){
    
    if (flag3==false){
      trigger_camera();  // start exposure
      flag3 = true;
      Serial.print("3-");
      Serial.println(millis());
    }
  }
  
  if(millis() > next_start + 400){
    
    if (flag4==false){
      digitalWrite(trigger_pin_IB,0);  // laser off
      set_z(0);
      flag4 = true;
      Serial.print("4-");
      Serial.println(millis());
    }
  }  

}

void sendWriteSPI(uint32_t registers, uint32_t valueX, uint32_t valueY){

  while(digitalRead(slaveReadyPin) == HIGH){}                         //wait for slave to be ready
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE1));
  digitalWrite(slaveSelectPin,LOW);
                           SPI.transfer(0x00);SPI.transfer(0x01);       //write command
  for(int i=24;i>-8;i=i-8){SPI.transfer((registers >> i) & 0xFF);}      //registers
  for(int i=24;i>-8;i=i-8){SPI.transfer((valueX >> i) & 0xFF);}         //X command
  for(int i=24;i>-8;i=i-8){SPI.transfer((valueY >> i) & 0xFF);}         //Y command
  digitalWrite(slaveSelectPin,HIGH);
  SPI.endTransaction();
  
}

void sendReadSPI(uint32_t Register){
  while(digitalRead(slaveReadyPin) == HIGH){}                         //wait for slave to be ready
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE1));
  digitalWrite(slaveSelectPin,LOW);
  SPI.transfer(0x00);SPI.transfer(0x00);     //read command
  SPI.transfer((Register >> 8) & 0xFF);      //register to read from byte 1
  SPI.transfer((Register) & 0xFF);           //register to read from byte 2
  for(int i=0;i<10;i++){
    data = SPI.transfer(0x00);               //send blank data bytes to fill the rest of the frame
    if(i==1){Serial.print(data);Serial.print("\t");}
  }
  
  digitalWrite(slaveSelectPin,HIGH);
  SPI.endTransaction();
}

uint32_t generateSPFPR(float f) {
  float normalized;
  int16_t shift;
  int32_t sign, exponent, significand;
 
  if (f == 0.0) 
    return 0; //handle this special case
  //check sign and begin normalization
  if (f < 0) { 
    sign = 1; 
    normalized = -f; 
  } else { 
    sign = 0; 
    normalized = f; 
  }
  //get normalized form of f and track the exponent
  shift = 0;
  while (normalized >= 2.0) { 
    normalized /= 2.0; 
    shift++; 
  }
  while (normalized < 1.0) { 
    normalized *= 2.0; 
    shift--; 
  }
  normalized = normalized - 1.0;
  //calculate binary form (non-float) of significand 
  significand = normalized*(0x800000 + 0.5f);
  //get biased exponent
  exponent = shift + 0x7f; //shift + bias
  //combine and return
  return (sign<<31) | (exponent<<23) | significand;
}
